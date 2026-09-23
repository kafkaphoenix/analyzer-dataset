from __future__ import annotations

from typing import Annotated, Any

import click
import typer
from pyarrow import parquet

from tiktok_dataset.config import Settings
from tiktok_dataset.queries import QUERIES
from tiktok_dataset.usecase.benchmark import benchmark

app = typer.Typer(
    name="tiktok-benchmark",
    help="Benchmark TikTok dataset query engines.",
)


@app.command()
def run(
    query_name: Annotated[
        str,
        typer.Option(
            "--query",
            "-q",
            help="Query engine to benchmark.",
            click_type=click.Choice(list(QUERIES.keys())),
        ),
    ],
    monitor_enabled: Annotated[
        bool,
        typer.Option(
            "--monitor",
            "-m",
            help="Enable monitoring of the query execution.",
        ),
    ] = False,
    cpu_batch_size: Annotated[
        int | None,
        typer.Option(
            "--cpu-batch-size",
            "-cb",
            help="Batch size to use for CPU queries.",
        ),
    ] = None,
    gpu_batch_size: Annotated[
        int | None,
        typer.Option(
            "--gpu-batch-size",
            "-gb",
            help="Batch size to use for GPU queries.",
        ),
    ] = None,
    cudf_chunk_read_limit: Annotated[
        int | None,
        typer.Option(
            "--cudf-chunk-read-limit",
            "-ccrl",
            help="Chunk read limit for cuDF.",
        ),
    ] = None,
    duckdb_threads: Annotated[
        int | None,
        typer.Option(
            "--duckdb-threads",
            "-dt",
            help="Number of threads to use for DuckDB.",
        ),
    ] = None,
) -> None:
    """Process the TikTok dataset with the selected query engine."""

    # Construct an overrides dictionary using only the explicitly passed CLI options
    overrides: dict[str, Any] = {}
    if cpu_batch_size is not None:
        overrides["default_batch_size_cpu"] = cpu_batch_size
    if gpu_batch_size is not None:
        overrides["default_batch_size_gpu"] = gpu_batch_size
    if cudf_chunk_read_limit is not None:
        overrides["cudf_chunk_read_limit_mib"] = cudf_chunk_read_limit
    if duckdb_threads is not None:
        overrides["duckdb_threads"] = duckdb_threads

    # Initialize Settings safely, letting Pydantic fall back to defaults/.env for missing options
    settings = Settings(**overrides)

    settings.results_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Extract target metadata parameters from the source parquet file header descriptor
    pt = parquet.ParquetFile(settings.dataset)
    total_rows = pt.metadata.num_rows

    query_builder = QUERIES[query_name]

    # Resolve target query engine factory instantiation matching your generic signature definitions.
    # Utilizing the bytes-based dynamic property for cuDF ensures proper hardware allocation.
    query = query_builder(
        parquet_path=settings.dataset,
        english_words_path=settings.english_words,
        english_stopwords_path=settings.english_stopwords,
        min_word_length=settings.min_word_length,
        top_k=settings.top_k,
        batch_size_cpu=settings.default_batch_size_cpu,
        batch_size_gpu=settings.default_batch_size_gpu,
        cudf_chunk_read_limit=settings.cudf_chunk_read_limit,
        duckdb_threads=settings.duckdb_threads,
    )

    # Launch performance profiling pipeline orchestration block
    benchmark(
        query=query,
        name=query_name,
        results_dir=settings.results_dir,
        runs_log=settings.results_dir / "runs.csv",
        total_rows=total_rows,
        monitor_enabled=monitor_enabled,
    )


if __name__ == "__main__":
    app()
