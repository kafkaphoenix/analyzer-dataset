from __future__ import annotations

from pathlib import Path
from typing import cast

import polars as pl

from tiktok_dataset.domain.tokenizer import (
    CLEAN_PATTERN,
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

    def _build_query(
        self,
        english_words: pl.LazyFrame,
        include_row_index: bool,
    ) -> pl.LazyFrame:
        # avoid selecting the row index column unless necessary for monitoring
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
                .str.to_lowercase()
                .str.replace_all(
                    CLEAN_PATTERN,
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
        """Per-chunk word aggregation, on GPU."""
        return batch.lazy().group_by("word").agg(pl.col("views").sum().alias("total_views")).collect(engine=GPU_ENGINE)

    @staticmethod
    def _finalize(partials: pl.DataFrame, top_k: int) -> pl.DataFrame:
        """
        Merge partial results and compute the top-k aggregation, on GPU.

        No `value_col` parameter here (unlike the CPU version) --
        every GPU path batches unconditionally and pre-aggregates
        each batch via `_aggregate_batch` first, so `partials`
        always already has `total_views`, never raw `views`.
        """
        return (
            partials.lazy()
            .group_by("word")
            .agg(pl.col("total_views").sum().alias("total_views"))
            .top_k(top_k, by="total_views")
            .sort("total_views", descending=True)
            .collect(engine=GPU_ENGINE)
        )

    def _collect(self, english_words: pl.LazyFrame) -> pl.DataFrame:
        """No monitoring, still batched (VRAM-bounded), but no row index/progress."""
        query = self._build_query(english_words, include_row_index=False)

        partial_results: list[pl.DataFrame] = []

        for batch in query.collect_batches(
            chunk_size=self.batch_size,
            maintain_order=False,
            engine="streaming",
        ):
            if batch.is_empty():
                continue

            partial_results.append(self._aggregate_batch(batch))

        if not partial_results:
            return pl.DataFrame(
                {"word": [], "total_views": []},
                schema={"word": pl.String, "total_views": pl.UInt64},
            )

        partials = pl.concat(partial_results, how="vertical")
        return self._finalize(partials, self.top_k)

    def _collect_monitored(self, english_words: pl.LazyFrame, progress: ProgressReporter) -> pl.DataFrame:
        """Monitored, batched, progress tracked by row index."""
        query = self._build_query(english_words, include_row_index=True)

        partial_results: list[pl.DataFrame] = []
        completed_rows = 0

        for batch in query.collect_batches(
            chunk_size=self.batch_size,
            maintain_order=False,
            engine="streaming",
        ):
            if not batch.is_empty():
                max_row_index = cast(int | None, batch[_ROW_INDEX_COL].max())
                if max_row_index is not None:
                    completed_rows = max(completed_rows, max_row_index + 1)
            progress.update(completed_rows)

            if batch.is_empty():
                continue

            batch = batch.drop(_ROW_INDEX_COL)
            partial_results.append(self._aggregate_batch(batch))

        if not partial_results:
            return pl.DataFrame(
                {"word": [], "total_views": []},
                schema={"word": pl.String, "total_views": pl.UInt64},
            )

        partials = pl.concat(partial_results, how="vertical")
        return self._finalize(partials, self.top_k)

    def collect(
        self,
        progress: ProgressReporter | None = None,
    ) -> pl.DataFrame:
        english_words = pl.DataFrame({"word": list(load_english_words(self.english_words_path))}).lazy()

        if progress is None:
            return self._collect(english_words)

        return self._collect_monitored(english_words, progress)


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
