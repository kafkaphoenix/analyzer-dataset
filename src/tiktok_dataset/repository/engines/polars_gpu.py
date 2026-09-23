from __future__ import annotations

from pathlib import Path
from typing import cast

import polars as pl

from tiktok_dataset.domain.tokenizer import WORD_PATTERN_POLARS
from tiktok_dataset.repository.engines.polars_common import clean_desc_polars
from tiktok_dataset.repository.vocabulary import (
    load_english_words,
)
from tiktok_dataset.usecase.query import ProgressReporter

ENGINE = "polars_gpu"

GPU_ENGINE = pl.GPUEngine(
    raise_on_fail=True,
)

_ROW_INDEX_COL = "_row_index"


class GPUQuery:
    """
    Hybrid Polars CPU/GPU query implementation.

    Text tokenization and regex processing run on the CPU via Polars
    Streaming because cuDF-Polars does not natively support the
    non-trivial regex expressions and complex list/explode operations
    required by the tokenizer.

    Once tokenized, both the per-chunk aggregation and the final
    merge/top-k/sort run on the cuDF GPU engine.

    Batching via `collect_batches` is unconditional in both paths,
    even without monitoring, because VRAM is a much tighter ceiling
    than system RAM. `explode()` can multiply the row count well
    beyond what a single unbounded GPU aggregation could safely hold.

    Only row-index tracking and progress callbacks differ between
    monitored and unmonitored execution.
    """

    def __init__(
        self,
        parquet_path: Path,
        english_words_path: Path,
        english_stopwords_path: Path,
        min_word_length: int,
        top_k: int,
        batch_size: int,
    ):
        self.parquet_path = parquet_path
        self.english_words_path = english_words_path
        self.english_stopwords_path = english_stopwords_path
        self.min_word_length = min_word_length
        self.top_k = top_k
        self.batch_size = batch_size

    def _build_execution_plan(
        self,
        english_words: pl.LazyFrame,
        include_row_index: bool,
    ) -> pl.LazyFrame:
        """
        Define the lazy transformation steps for reading, tokenizing,
        and filtering text.

        The tokenization stage is deliberately executed using the
        shared native Polars cleaning implementation. The resulting
        plan is then consumed in streaming batches, with GPU execution
        used for the aggregation stages.
        """
        keep = [_ROW_INDEX_COL] if include_row_index else []

        return (
            pl.scan_parquet(
                self.parquet_path,
                row_index_name=(_ROW_INDEX_COL if include_row_index else None),
            )
            .select(
                *keep,
                "views",
                "desc",
            )
            .filter(pl.col("desc").is_not_null() & pl.col("views").is_not_null())
            .with_columns(
                clean_desc_polars(
                    pl.col("desc"),
                )
                .str.extract_all(
                    WORD_PATTERN_POLARS,
                )
                .list.unique()
                .alias("word")
            )
            .select(
                *keep,
                "views",
                "word",
            )
            .explode(
                "word",
                empty_as_null=False,
            )
            .join(
                english_words,
                on="word",
                how="semi",
            )
            .select(
                *keep,
                "views",
                "word",
            )
        )

    @staticmethod
    def _aggregate_batch(
        batch: pl.DataFrame,
    ) -> pl.DataFrame:
        """
        Perform an immediate eager aggregation of the current batch
        on the GPU.

        Consolidating the exploded data immediately down to unique
        words and view sums prevents RAM/VRAM exhaustion caused by
        text expansion.
        """
        return (
            batch.lazy()
            .group_by("word")
            .agg(pl.col("views").sum().alias("total_views"))
            .collect(
                engine=GPU_ENGINE,
            )
        )

    @staticmethod
    def _finalize(
        partials: pl.LazyFrame,
        top_k: int,
    ) -> pl.DataFrame:
        """
        Merge the per-batch results and perform the final Top-K
        aggregation and sorting on the GPU.
        """
        return (
            partials.group_by("word")
            .agg(pl.col("total_views").sum().alias("total_views"))
            .top_k(
                top_k,
                by="total_views",
            )
            .sort(
                "total_views",
                descending=True,
            )
            .collect(
                engine=GPU_ENGINE,
            )
        )

    def _process_stream(
        self,
        english_words: pl.LazyFrame,
        progress: ProgressReporter | None = None,
    ) -> pl.DataFrame:
        """
        Process the dataset through streaming chunks and aggregate
        results.

        Each chunk is eagerly aggregated on the GPU before the next
        chunk is processed, keeping RAM and VRAM bounded.

        When monitoring is enabled, the row index stamped at scan time
        is used to report the true input-file progress.
        """
        include_row_index = progress is not None

        query = self._build_execution_plan(
            english_words,
            include_row_index=include_row_index,
        )

        partial_results: list[pl.DataFrame] = []
        completed_rows = 0

        for batch in query.collect_batches(
            chunk_size=self.batch_size,
            maintain_order=False,
            engine="streaming",
        ):
            if batch.is_empty():
                if progress is not None:
                    progress.update(completed_rows)
                continue

            if progress is not None:
                max_row_index = cast(
                    int | None,
                    batch[_ROW_INDEX_COL].max(),
                )

                if max_row_index is not None:
                    completed_rows = max(
                        completed_rows,
                        max_row_index + 1,
                    )

                batch = batch.drop(
                    _ROW_INDEX_COL,
                )

                progress.update(
                    completed_rows,
                )

            partial_results.append(self._aggregate_batch(batch))

        if not partial_results:
            return pl.DataFrame(
                {
                    "word": [],
                    "total_views": [],
                },
                schema={
                    "word": pl.String,
                    "total_views": pl.UInt64,
                },
            )

        partials = pl.concat(
            partial_results,
            how="vertical",
        )

        return self._finalize(
            partials.lazy(),
            self.top_k,
        )

    def collect(
        self,
        progress: ProgressReporter | None = None,
    ) -> pl.DataFrame:
        """
        Public entry point to resolve the dataset query.

        Tokenization is performed through the shared Polars cleaning
        implementation, while batch and final aggregations are
        executed using the cuDF-backed GPU engine.
        """
        english_words = pl.DataFrame(
            {
                "word": list(
                    load_english_words(
                        self.english_words_path,
                        self.english_stopwords_path,
                        min_word_length=self.min_word_length,
                    )
                )
            }
        ).lazy()

        return self._process_stream(
            english_words,
            progress=progress,
        )


def build_query(
    parquet_path: Path,
    english_words_path: Path,
    top_k: int,
    english_stopwords_path: Path,
    min_word_length: int,
    batch_size: int,
    **_: object,
) -> GPUQuery:
    return GPUQuery(
        parquet_path=parquet_path,
        english_words_path=english_words_path,
        top_k=top_k,
        english_stopwords_path=english_stopwords_path,
        min_word_length=min_word_length,
        batch_size=batch_size,
    )
