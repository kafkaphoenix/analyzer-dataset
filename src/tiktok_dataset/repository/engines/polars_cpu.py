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

ENGINE = "cpu"

_ROW_INDEX_COL = "_row_index"


class CPUQuery:
    """
    CPU Polars implementation.

    Parquet scanning, tokenization, dictionary filtering and
    aggregation are performed using Polars on the CPU.

    Normal path: one fused query, no row index, no batching overhead.

    Monitored path: chunked via `collect_batches`, but progress
    is tracked from a `_row_index` column stamped at scan time,
    not from `batch.height` -- `chunk_size` counts OUTPUT rows
    (post explode/join), which misrepresents how much of the
    file was actually scanned. `max(row_index)` gives the true
    input-row position regardless of how much explode inflated
    or the join dropped. This also makes `maintain_order=False`
    safe, since progress no longer assumes batches arrive in
    file order.
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
        it. It will be resolved using Polars' streaming engine on the CPU.
        """
        # Avoid selecting the row index column unless necessary for monitoring
        keep = [_ROW_INDEX_COL] if include_row_index else []

        scan = pl.scan_parquet(
            self.parquet_path,
            row_index_name=_ROW_INDEX_COL if include_row_index else None,
        )

        return (
            scan.select(
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
    def _finalize(
        partials: pl.LazyFrame,
        top_k: int,
        value_col: str = "total_views",
    ) -> pl.DataFrame:
        """
        Processes the unified LazyFrame using the streaming engine to run the final
        group-by, Top-K extraction, and sorting.
        """
        return (
            partials.group_by("word")
            .agg(pl.col(value_col).sum().alias("total_views"))
            .top_k(top_k, by="total_views")
            .sort("total_views", descending=True)
            .collect(engine="streaming")
        )

    def _collect(
        self,
        english_words: pl.LazyFrame,
    ) -> pl.DataFrame:
        """
        Execute a single fused lazy query over the entire file on the CPU.
        Bypasses batching entirely when no monitoring is requested, allowing
        Polars to optimize memory mapping and streaming allocations natively.
        """
        return self._finalize(
            self._build_execution_plan(english_words, include_row_index=False),
            self.top_k,
            value_col="views",
        )

    def _collect_monitored(
        self,
        english_words: pl.LazyFrame,
        progress: ProgressReporter,
    ) -> pl.DataFrame:
        """
        Execute the query through streaming chunks with real-time progress monitoring.
        Tracks actual read performance by extracting the maximum row index position
        stamped at scan time from the stream. Chunks are aggregated eagerly inside
        the loop to maintain an unbloated RAM footprint.
        """
        query = self._build_execution_plan(english_words, include_row_index=True)

        partial_results: list[pl.DataFrame] = []
        completed_rows = 0

        for batch in query.collect_batches(
            chunk_size=self.batch_size,
            maintain_order=False,
            engine="streaming",
        ):
            if batch.is_empty():
                progress.update(completed_rows)
                continue

            max_row_index = cast(int | None, batch[_ROW_INDEX_COL].max())
            if max_row_index is not None:
                completed_rows = max(
                    completed_rows,
                    max_row_index + 1,
                )

            # Eagerly aggregate the chunk to keep memory consumption low
            partial_results.append(batch.drop(_ROW_INDEX_COL).group_by("word").agg(pl.col("views").sum().alias("total_views")))

            progress.update(completed_rows)

        if not partial_results:
            return pl.DataFrame(
                {"word": [], "total_views": []},
                schema={"word": pl.String, "total_views": pl.UInt64},
            )

        # Merge eager DataFrames and feed them into _finalize as a lazy frame
        partials = pl.concat(partial_results, how="vertical")
        return self._finalize(partials.lazy(), self.top_k, value_col="total_views")

    def collect(
        self,
        progress: ProgressReporter | None = None,
    ) -> pl.DataFrame:
        """
        Public entry point to resolve the dataset query on the CPU.
        """
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
) -> CPUQuery:
    return CPUQuery(
        parquet_path=parquet_path,
        english_words_path=english_words_path,
        top_k=top_k,
        batch_size=batch_size,
    )
