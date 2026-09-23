from __future__ import annotations

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
from tiktok_dataset.usecase.query import Query, QueryBuilder


def build_cpu(
    parquet_path: Path,
    english_words_path: Path,
    english_stopwords_path: Path,
    min_word_length: int,
    top_k: int,
    batch_size_cpu: int,
    **_: object,
) -> Query:
    """Factory builder for the Polars CPU streaming query engine."""
    return CPUQuery(
        parquet_path=parquet_path,
        english_words_path=english_words_path,
        top_k=top_k,
        english_stopwords_path=english_stopwords_path,
        min_word_length=min_word_length,
        batch_size=batch_size_cpu,
    )


def build_polars_gpu(
    parquet_path: Path,
    english_words_path: Path,
    english_stopwords_path: Path,
    min_word_length: int,
    top_k: int,
    batch_size_gpu: int,
    **_: object,
) -> Query:
    """Factory builder for the Polars Hybrid GPU execution plan engine."""
    return GPUQuery(
        parquet_path=parquet_path,
        english_words_path=english_words_path,
        top_k=top_k,
        english_stopwords_path=english_stopwords_path,
        min_word_length=min_word_length,
        batch_size=batch_size_gpu,
    )


def build_cudf(
    parquet_path: Path,
    english_words_path: Path,
    english_stopwords_path: Path,
    min_word_length: int,
    top_k: int,
    cudf_chunk_read_limit: int,
    **_: object,
) -> Query:
    """Factory builder for the native GPU cuDF/libcudf streaming engine."""
    return GPUCUDFQuery(
        parquet_path=parquet_path,
        english_words_path=english_words_path,
        english_stopwords_path=english_stopwords_path,
        min_word_length=min_word_length,
        top_k=top_k,
        chunk_read_limit=cudf_chunk_read_limit,
    )


def build_duckdb(
    parquet_path: Path,
    english_words_path: Path,
    english_stopwords_path: Path,
    min_word_length: int,
    top_k: int,
    duckdb_threads: int,
    **_: object,
) -> Query:
    """Factory builder for the DuckDB analytical vector streaming engine."""
    return DuckDBQuery(
        parquet_path=parquet_path,
        english_words_path=english_words_path,
        english_stopwords_path=english_stopwords_path,
        min_word_length=min_word_length,
        top_k=top_k,
        threads=duckdb_threads,
    )


# Central registry map linking engine option string tokens to their respective factory definitions.
# This matrix satisfies type constraints defined within the QueryBuilder structural protocol.
QUERIES: dict[str, QueryBuilder] = {
    "cpu": build_cpu,
    "gpu": build_polars_gpu,
    "cudf": build_cudf,
    "duckdb": build_duckdb,
}
