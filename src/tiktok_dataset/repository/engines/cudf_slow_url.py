from __future__ import annotations

from pathlib import Path

import cudf
import polars as pl
import pylibcudf as plc

from tiktok_dataset.domain.tokenizer import (
    ASCII_LOWER_MAP,
    CLEAN_PATTERN_CUDF,
    WORD_PATTERN_CUDF,
)
from tiktok_dataset.repository.vocabulary import (
    load_english_words,
)
from tiktok_dataset.usecase.query import ProgressReporter

ENGINE = "cudf"


class GPUCUDFQuery:
    """
    Native cuDF implementation.

    Parquet reading, tokenization, dictionary filtering and
    aggregation are performed entirely on the GPU using libcudf and cuDF.
    """

    def __init__(
        self,
        parquet_path: Path,
        english_words_path: Path,
        top_k: int,
        chunk_read_limit: int,
    ):
        self.parquet_path = parquet_path
        self.english_words_path = english_words_path
        self.top_k = top_k
        self.chunk_read_limit = chunk_read_limit

    @staticmethod
    def _process_dataframe(
        df: cudf.DataFrame,
        english_words: cudf.DataFrame,
    ) -> cudf.DataFrame | None:
        """
        Tokenize text, filter against the vocabulary, and aggregate views per batch on the GPU.
        This handles string normalization, regex findall extractions, array flattening (explode),
        and vocabulary semi-joins natively using GPU kernels.
        """
        df = df.dropna(subset=["desc", "views"])
        if len(df) == 0:
            return None

        # Architectural Note: `.str.translate` is chosen here because we are performing a
        # strict 1-to-1 character lookup map (A-Z to a-z), which maps perfectly to a blazing-fast
        # CUDA array lookup kernel.
        #
        # If we ever need to replace arbitrary multi-character substrings of varying lengths
        # (e.g., replacing 'sub1' -> 'rep1', 'substring2' -> 'rep2'), `.str.translate` cannot
        # handle it. In that specific scenario, we would instead use `.str.replace_many`,
        # which is cuDF's native, highly parallelized solution for bulk substring replacement
        # without launching multiple costly sequential `.str.replace` iterations.
        desc = df["desc"].str.translate(ASCII_LOWER_MAP).str.replace(CLEAN_PATTERN_CUDF, " ", regex=True)

        # Extract words and keep unique tokens per description row
        words = desc.str.findall(WORD_PATTERN_CUDF).list.unique()

        df = cudf.DataFrame({"views": df["views"], "word": words})

        # Explode arrays into individual rows and drop null/empty tokens
        df = df.explode("word", ignore_index=True).dropna(subset=["word"])
        if len(df) == 0:
            return None

        # Filter tokens against the English vocabulary dictionary
        df = df.merge(english_words, on="word", how="inner")
        if len(df) == 0:
            return None

        # Pre-aggregate views per word to drastically minimize final merge footprint
        # Cast to uint64 because sum returns int64 even when the input is uint64.
        return df.groupby("word", sort=False)["views"].sum().reset_index(name="total_views").astype({"total_views": "uint64"})

    def _process_stream(
        self,
        english_words: cudf.DataFrame,
        progress: ProgressReporter | None = None,
    ) -> cudf.DataFrame:
        """
        Stream Parquet chunks via pylibcudf, updating progress and collecting GPU partial sums.
        """
        source = plc.io.SourceInfo([str(self.parquet_path)])

        options = (
            plc.io.parquet.ParquetReaderOptions.builder(source)  # type: ignore[attr-defined]
            .column_names(["views", "desc"])
            .build()
        )

        reader = plc.io.parquet.ChunkedParquetReader(
            options,
            chunk_read_limit=self.chunk_read_limit,
        )

        partial_results: list[cudf.DataFrame] = []
        completed_rows = 0

        while reader.has_next():
            table = reader.read_chunk()
            df = cudf.DataFrame.from_pylibcudf(table)

            # Update the scanner progress based on the raw chunk sizes read from disk
            if progress is not None:
                completed_rows += len(df)
                progress.update(completed_rows)

            partial = self._process_dataframe(df, english_words)
            if partial is not None and len(partial) > 0:
                partial_results.append(partial)

        if not partial_results:
            return cudf.DataFrame(
                {"word": [], "total_views": []},
                dtype={"word": "object", "total_views": "uint64"},
            )

        return cudf.concat(partial_results, ignore_index=True)

    @staticmethod
    def _finalize(partials: cudf.DataFrame, top_k: int) -> pl.DataFrame:
        """
        Merge intermediate stream reductions and compute the global Top-K on the GPU.
        Aggregates the vertically stacked cuDF results, sorts them, extracts the top-K
        records, and exports the final matrix into a Polars DataFrame via PyArrow.
        """
        if len(partials) == 0:
            return pl.DataFrame(
                {"word": [], "total_views": []},
                schema={"word": pl.String, "total_views": pl.UInt64},
            )

        # Cast to uint64 because sum returns int64 even when the input is uint64.
        final = partials.groupby("word", sort=False)["total_views"].sum().reset_index().astype({"total_views": "uint64"})

        final = final.sort_values("total_views", ascending=False).head(top_k).reset_index(drop=True)

        return pl.DataFrame(final.to_arrow())

    def collect(
        self,
        progress: ProgressReporter | None = None,
    ) -> pl.DataFrame:
        """
        Public entry point to resolve the dataset query natively on the GPU via cuDF.
        """
        english_words = cudf.DataFrame({"word": list(load_english_words(self.english_words_path))})
        partials = self._process_stream(english_words, progress=progress)
        return self._finalize(partials, self.top_k)


def build_query(
    parquet_path: Path,
    english_words_path: Path,
    top_k: int,
    cudf_chunk_read_limit: int,
    **_: object,
) -> GPUCUDFQuery:
    return GPUCUDFQuery(
        parquet_path=parquet_path,
        english_words_path=english_words_path,
        top_k=top_k,
        chunk_read_limit=cudf_chunk_read_limit,
    )
