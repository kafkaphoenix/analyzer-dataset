from __future__ import annotations

import csv
import time
from pathlib import Path

import polars as pl

from tiktok_dataset.usecase.monitor import ProcessMonitor
from tiktok_dataset.usecase.query import Query


def benchmark(
    query: Query,
    name: str,
    results_dir: Path,
    runs_log: Path,
    total_rows: int,
    monitor_enabled: bool = True,
) -> pl.DataFrame:
    """
    Execute an analytical engine query and record accurate runtime performance metrics.
    """
    results_dir.mkdir(parents=True, exist_ok=True)

    monitor: ProcessMonitor | None = None
    if monitor_enabled:
        monitor = ProcessMonitor(engine=name, total_rows=total_rows)

    try:
        # OPTIMIZATION FIXED: Spin up the UI loop and heavy OS metrics collection BEFORE
        # starting the performance clock to eliminate initialization noise from benchmarks.
        if monitor is not None:
            monitor.start()

        # Start the clock on pure data processing only
        start = time.perf_counter()
        result = query.collect(progress=monitor)
        elapsed = time.perf_counter() - start

    finally:
        # Pass failure state down to prevent forcing a misleading 100% UI screen on exceptions
        if monitor is not None:
            monitor.stop()

    # Cache target outcome matrix into persistent parquet block storage
    result.write_parquet(results_dir / f"{name}.parquet")

    _print_result(name=name, result=result, elapsed=elapsed)
    _write_run_log(path=runs_log, engine=name, elapsed=elapsed, result=result)

    return result


def _print_result(name: str, result: pl.DataFrame, elapsed: float) -> None:
    """Flush the computed top-K records output layout matrix to the stdout terminal standard view."""
    print(f"\n=== {name} ===\n\n{result}\n\nQuery time: {elapsed:.2f}s")


def _write_run_log(path: Path, engine: str, elapsed: float, result: pl.DataFrame) -> None:
    """
    Append an incremental run summary record row directly inside the persistent CSV logfile.
    """
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a+", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["engine", "elapsed_seconds", "top_word", "top_views"],
        )

        file.seek(0, 2)  # Go to the end of the file safely to prevent multi-process append corruption
        if file.tell() == 0:
            writer.writeheader()

        top_word = ""
        top_views = ""

        # Safely extract leading target top-K token if the result is valid
        if not result.is_empty():
            top_word = str(result.item(0, "word"))
            top_views = str(result.item(0, "total_views"))

        writer.writerow(
            {
                "engine": engine,
                "elapsed_seconds": f"{elapsed:.6f}",
                "top_word": top_word,
                "top_views": top_views,
            }
        )
