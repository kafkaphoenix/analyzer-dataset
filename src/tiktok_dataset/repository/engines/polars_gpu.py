from __future__ import annotations

from pathlib import Path
from typing import cast

import polars as pl

from tiktok_dataset.domain.tokenizer import (
    ASCII_LOWER_MAP,
    CLEAN_PATTERN_POLARS,
    WORD_PATTERN,
)
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

    Text tokenization and regex processing run on the CPU via Polars Streaming
    because cuDF-Polars does not natively support non-trivial regex expressions
    and complex list/explode operations on GPU. Once tokenized, both the
    per-chunk aggregation and the final merge/top-k/sort run on the cuDF
    GPU engine.

    Batching via `collect_batches` is unconditional in BOTH paths -- even
    without monitoring -- because VRAM is a much tighter ceiling than
    system RAM, and `explode()` can multiply row count well past what a
    single unbounded GPU aggregation call could safely hold. Only the
    row-index tracking and progress callbacks differ between the two paths.
    """

    def __init__(
        self,
        parquet_path: Path,
        english_words_path: Path,
        top_k: int,
        batch_size: int,
    ):
        self.parquet_path = parquet_path
        self.english_words_path = english_words_path
        self.top_k = top_k
        self.batch_size = batch_size

    def _build_execution_plan(
        self,
        english_words: pl.LazyFrame,
        include_row_index: bool,
    ) -> pl.LazyFrame:
        """
        Define the lazy transformation steps for reading, tokenizing, and filtering text.
        This method constructs the logical execution plan (or recipe) without executing
        it. This specific pipeline is assigned to run on the CPU because the streaming
        engine handles complex string manipulations, regex extractions, list operations,
        and dictionary semi-joins which are not supported on the GPU.
        """
        # Avoid selecting the row index column unless necessary for monitoring
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
                pl.col("desc")
                .str.replace_many(
                    ASCII_LOWER_MAP,
                )
                .str.replace_all(
                    CLEAN_PATTERN_POLARS,
                    " ",
                )
                .str.extract_all(
                    WORD_PATTERN,
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
    def _aggregate_batch(batch: pl.DataFrame) -> pl.DataFrame:
        """
        Perform an immediate, eager aggregation of the current batch on the GPU.
        Consolidating the data immediately down to unique words and view sums
        prevents RAM/VRAM exhaustion caused by exploded text expansions. Returning
        an eager DataFrame here bypasses massive Polars lazy-plan optimization
        overhead when concatenating thousands of loops later.
        """
        return batch.lazy().group_by("word").agg(pl.col("views").sum().alias("total_views")).collect(engine=GPU_ENGINE)

    @staticmethod
    def _finalize(partials: pl.LazyFrame, top_k: int) -> pl.DataFrame:
        """
        Processes the unified LazyFrame using the cuDF engine to run the final
        group-by, Top-K extraction, and sorting on the GPU.
        """
        return (
            partials.group_by("word")
            .agg(pl.col("total_views").sum().alias("total_views"))
            .top_k(top_k, by="total_views")
            .sort("total_views", descending=True)
            .collect(engine=GPU_ENGINE)
        )

    def _process_stream(self, english_words: pl.LazyFrame, progress: ProgressReporter | None = None) -> pl.DataFrame:
        """
        Process the dataset through streaming chunks and aggregate results.
        If a progress reporter is provided, it tracks real-time scanning metrics
        via the row index stamped at scan time. Each chunk is eagerly aggregated
        on the GPU inside the loop to tightly bound RAM/VRAM consumption.
        """
        include_row_index = progress is not None
        query = self._build_execution_plan(english_words, include_row_index=include_row_index)

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
                # Read true scanner progress via row index before dropping it
                max_row_index = cast(int | None, batch[_ROW_INDEX_COL].max())
                if max_row_index is not None:
                    completed_rows = max(completed_rows, max_row_index + 1)

                batch = batch.drop(_ROW_INDEX_COL)
                progress.update(completed_rows)

            partial_results.append(self._aggregate_batch(batch))

        if not partial_results:
            return pl.DataFrame(
                {"word": [], "total_views": []},
                schema={"word": pl.String, "total_views": pl.UInt64},
            )

        # Merge eager DataFrames and feed them into _finalize as a lazy frame
        partials = pl.concat(partial_results, how="vertical")
        return self._finalize(partials.lazy(), self.top_k)

    def collect(
        self,
        progress: ProgressReporter | None = None,
    ) -> pl.DataFrame:
        """
        Public entry point to resolve the dataset query.
        Routes the lazy graph generation and unified streaming loop to produce
        the final top-K matching English words dataframe.
        """
        english_words = pl.DataFrame({"word": list(load_english_words(self.english_words_path))}).lazy()

        return self._process_stream(english_words, progress=progress)


def build_query(
    parquet_path: Path,
    english_words_path: Path,
    top_k: int,
    batch_size: int,
    **_: object,
) -> GPUQuery:
    return GPUQuery(
        parquet_path=parquet_path,
        english_words_path=english_words_path,
        top_k=top_k,
        batch_size=batch_size,
    )
