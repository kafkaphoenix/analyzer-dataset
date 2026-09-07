from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WordResult:
    word: str
    total_views: int
