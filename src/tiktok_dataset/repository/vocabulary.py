from __future__ import annotations

from pathlib import Path


def load_english_words(path: Path) -> set[str]:
    """Load and normalize the English vocabulary."""

    words: set[str] = set()

    with path.open(
        "r",
        encoding="utf-8",
        errors="ignore",
    ) as file:
        for line in file:
            word = line.strip().lower()

            if len(word) >= 3 and word.isascii() and word.isalpha():
                words.add(word)

    return words
