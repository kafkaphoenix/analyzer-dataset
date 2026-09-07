from __future__ import annotations

from pathlib import Path

import cudf
import polars as pl
import pylibcudf as plc

from tiktok_dataset.domain.tokenizer import (
    CLEAN_PATTERN,
    WORD_PATTERN,
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
    aggregation are performed using libcudf/cuDF.
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

        df = df.dropna(
            subset=[
                "desc",
                "views",
            ]
        )

        if len(df) == 0:
            return None

        desc = (
            df["desc"]
            .str.lower()
            .str.replace(
                CLEAN_PATTERN,
                " ",
                regex=True,
            )
        )

        words = desc.str.findall(WORD_PATTERN).list.unique()

        df = cudf.DataFrame(
            {
                "views": df["views"],
                "word": words,
            }
        )

        df = df.explode(
            "word",
            ignore_index=True,
        ).dropna(subset=["word"])

        if len(df) == 0:
            return None

        df = df.merge(
            english_words,
            on="word",
            how="inner",
        )

        if len(df) == 0:
            return None

        return (
            df.groupby(
                "word",
                sort=False,
            )["views"]
            .sum()
            .reset_index(name="total_views")
        )

    def collect(
        self,
        progress: ProgressReporter | None = None,
    ) -> pl.DataFrame:
        english_words = cudf.DataFrame({"word": list(load_english_words(self.english_words_path))})

        source = plc.io.SourceInfo([str(self.parquet_path)])

        options = (
            plc.io.parquet.ParquetReaderOptions.builder(source)  # type: ignore[attr-defined]
            .column_names(
                [
                    "views",
                    "desc",
                ]
            )
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

            if progress is not None:
                completed_rows += len(df)
                progress.update(completed_rows)

            partial = self._process_dataframe(
                df,
                english_words,
            )

            if partial is not None and len(partial) > 0:
                partial_results.append(partial)

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

        combined: cudf.DataFrame = cudf.concat(
            partial_results,
            ignore_index=True,
        )

        final: cudf.DataFrame = (
            combined.groupby(
                "word",
                sort=False,
            )["total_views"]
            .sum()
            .reset_index()
        )

        final = (
            final.sort_values(
                "total_views",
                ascending=False,
            )
            .head(self.top_k)
            .reset_index(drop=True)
        )

        return pl.DataFrame(final.to_arrow())


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
