from __future__ import annotations

import time
from typing import TYPE_CHECKING

from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

if TYPE_CHECKING:
    from analyzer_dataset.repository.system_monitor import (
        SystemMetrics,
        SystemMonitor,
    )


class ProcessMonitor:
    """
    Rich progress display for process execution.

    Receives row progress from the query and periodically
    samples CPU, RAM, threads and GPU metrics.
    """

    def __init__(
        self,
        engine: str,
        total_rows: int,
    ) -> None:
        self.engine = engine
        self.total_rows = total_rows

        self.completed_rows = 0
        self.start_time: float | None = None

        self._system_monitor: SystemMonitor | None = None
        self._live: Live | None = None

        self._progress = Progress(
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>6.2f}%"),
            TimeElapsedColumn(),
        )

        self._task_id = self._progress.add_task(
            engine,
            total=total_rows,
        )

        self._last_metrics: SystemMetrics | None = None
        self._last_metrics_time = 0.0
        self._metrics_sample_interval = 0.3

    def start(self) -> None:
        """Start the live view and initialize system monitoring."""
        from analyzer_dataset.repository.system_monitor import (
            SystemMonitor,
        )

        self.start_time = time.perf_counter()
        self._system_monitor = SystemMonitor().__enter__()

        self._refresh_metrics()
        self._last_metrics_time = self.start_time

        self._live = Live(
            self._render(),
            refresh_per_second=5,
        )
        self._live.start()

    def update(
        self,
        completed_rows: int,
        total_rows: int | None = None,
    ) -> None:
        """Update process progress based on rows processed."""
        self.completed_rows = completed_rows

        if total_rows is not None:
            self.total_rows = total_rows

        self._progress.update(
            self._task_id,
            completed=self.completed_rows,
            total=self.total_rows,
        )

        self._maybe_refresh_metrics()

    def update_percentage(self, percentage: float) -> None:
        """Update process progress based on a float percentage."""
        percentage = max(0.0, min(100.0, percentage))
        self.completed_rows = int(self.total_rows * percentage / 100.0)

        self._progress.update(
            self._task_id,
            completed=self.completed_rows,
            total=self.total_rows,
        )

        self._maybe_refresh_metrics()

    def stop(self) -> None:
        """Gracefully close monitoring and finish at 100%."""
        if self.total_rows > 0:
            self.completed_rows = self.total_rows

        self._progress.update(
            self._task_id,
            completed=self.total_rows,
        )

        self._refresh_metrics()
        self._refresh()

        if self._live is not None:
            self._live.stop()
            self._live = None

        if self._system_monitor is not None:
            self._system_monitor.__exit__(
                None,
                None,
                None,
            )
            self._system_monitor = None

    def _maybe_refresh_metrics(self) -> None:
        """Refresh system metrics when the sampling interval expires."""
        current_time = time.perf_counter()

        if current_time - self._last_metrics_time >= self._metrics_sample_interval:
            self._refresh_metrics()
            self._last_metrics_time = current_time
            self._refresh()

    def _refresh_metrics(self) -> None:
        """Capture the latest system metrics."""
        if self._system_monitor is None:
            return

        self._last_metrics = self._system_monitor.sample()

    def _refresh(self) -> None:
        """Force an immediate Rich layout refresh."""
        if self._live is not None:
            self._live.update(self._render())

    def _render(self) -> Group:
        """Generate the Rich Live UI."""
        elapsed = 0.0

        if self.start_time is not None:
            elapsed = time.perf_counter() - self.start_time

        if self.total_rows > 0:
            percentage = self.completed_rows / self.total_rows * 100
        else:
            percentage = 0.0

        rows = f"{self.completed_rows:,} / {self.total_rows:,}"

        table = Table.grid(padding=(0, 2))
        table.add_row("Rows", rows)
        table.add_row(
            "Progress",
            f"{percentage:.2f}%",
        )
        table.add_row(
            "Elapsed",
            f"{elapsed:.1f}s",
        )

        metrics = self._last_metrics

        if metrics is not None:
            table.add_row(
                "CPU",
                f"{metrics.cpu_percent:.1f}%",
            )
            table.add_row(
                "Threads",
                str(metrics.process_threads),
            )
            table.add_row(
                "CPU Temp",
                f"{metrics.cpu_temperature:.0f}°C",
            )
            table.add_row(
                "RAM",
                (f"{metrics.memory_used_gb:.1f} / {metrics.memory_total_gb:.1f} GB ({metrics.memory_percent:.1f}%)"),
            )

            if metrics.gpu_available:
                table.add_row(
                    "GPU",
                    f"{metrics.gpu_utilization:.1f}%",
                )
                table.add_row(
                    "VRAM",
                    (
                        f"{metrics.gpu_memory_used_gb:.1f} / "
                        f"{metrics.gpu_memory_total_gb:.1f} GB "
                        f"({metrics.gpu_memory_percent:.1f}%)"
                    ),
                )
                table.add_row(
                    "GPU Temp",
                    f"{metrics.gpu_temperature:.0f}°C",
                )
            else:
                table.add_row("GPU", "N/A")

        return Group(
            Panel(
                self._progress,
                title=f"[bold]{self.engine}[/bold]",
            ),
            Panel(
                table,
                title="System",
            ),
        )
