from __future__ import annotations

import csv
import time
from pathlib import Path

import polars as pl

from tiktok_dataset.usecase.query import Query

from tiktok_dataset.usecase.monitor import ProcessMonitor


def benchmark(
    query: Query,
    name: str,
    results_dir: Path,
    runs_log: Path,
    total_rows: int,
    monitor_enabled: bool = True,
) -> pl.DataFrame:
    """
    Execute a query and record benchmark information.
    """
    results_dir.mkdir(parents=True, exist_ok=True)

    monitor: ProcessMonitor | None = None
    if monitor_enabled:
        monitor = ProcessMonitor(engine=name, total_rows=total_rows)

    start = time.perf_counter()

    try:
        if monitor is not None:
            monitor.start()

        result = query.collect(progress=monitor)

    finally:
        if monitor is not None:
            monitor.stop()

    elapsed = time.perf_counter() - start

    result.write_parquet(results_dir / f"{name}.parquet")

    _print_result(name=name, result=result, elapsed=elapsed)
    _write_run_log(path=runs_log, engine=name, elapsed=elapsed, result=result)

    return result


def _print_result(name: str, result: pl.DataFrame, elapsed: float) -> None:
    print(f"\n=== {name} ===\n\n{result}\n\nQuery time: {elapsed:.2f}s")


def _write_run_log(path: Path, engine: str, elapsed: float, result: pl.DataFrame) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a+", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["engine", "elapsed_seconds", "top_word", "top_views"],
        )

        file.seek(0, 2)  # Go to the end of the file safely
        if file.tell() == 0:
            writer.writeheader()

        top_word = ""
        top_views = ""

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
