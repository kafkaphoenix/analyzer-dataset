from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import polars as pl


class ProgressReporter(Protocol):
    def update(self, completed_rows: int) -> None:
        """Report absolute completed rows."""
        ...

    def update_percentage(self, percentage: float) -> None:
        """Report absolute progress percentage."""
        ...


class Query(Protocol):
    def collect(
        self,
        progress: ProgressReporter | None = None,
    ) -> pl.DataFrame:
        """Execute the query and return the result."""
        ...


QueryBuilder = Callable[..., Query]
