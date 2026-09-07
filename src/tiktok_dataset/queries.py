from __future__ import annotations

import typing
from pathlib import Path

from tiktok_dataset.repository.engines.cudf import (
    GPUCUDFQuery,
)
from tiktok_dataset.repository.engines.duckdb import (
    DuckDBQuery,
)
from tiktok_dataset.repository.engines.polars_cpu import (
    CPUQuery,
)
from tiktok_dataset.repository.engines.polars_gpu import (
    GPUQuery,
)


def build_cpu(
    parquet_path: Path,
    english_words_path: Path,
    top_k: int,
    batch_size_cpu: int,
    **_: object,
) -> CPUQuery:
    return CPUQuery(
        parquet_path=parquet_path,
        english_words_path=english_words_path,
        top_k=top_k,
        batch_size=batch_size_cpu,
    )


def build_polars_gpu(
    parquet_path: Path,
    english_words_path: Path,
    top_k: int,
    batch_size_gpu: int,
    **_: object,
) -> GPUQuery:
    return GPUQuery(
        parquet_path=parquet_path,
        english_words_path=english_words_path,
        top_k=top_k,
        batch_size=batch_size_gpu,
    )


def build_cudf(
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


def build_duckdb(
    parquet_path: Path,
    english_words_path: Path,
    top_k: int,
    duckdb_threads: int | None,
    **_: object,
) -> DuckDBQuery:
    return DuckDBQuery(
        parquet_path=parquet_path,
        english_words_path=english_words_path,
        top_k=top_k,
        threads=duckdb_threads,
    )


QUERIES: dict[str, typing.Callable] = {
    "cpu": build_cpu,
    "gpu": build_polars_gpu,
    "cudf": build_cudf,
    "duckdb": build_duckdb,
}
