from __future__ import annotations

from pathlib import Path


def load_english_words(path: Path) -> set[str]:
    """
    Load, filter, and normalize the English vocabulary dictionary.
    Guarantees that only clean, lower-case, ASCII-only alphabetic tokens with a
    minimum length of 3 characters are preserved, aligning perfectly with the
    analytical query engines' tokenization filters.
    """
    words: set[str] = set()

    with path.open(
        "r",
        encoding="utf-8",
        errors="ignore",
    ) as file:
        for line in file:
            word = line.strip()

            # Filter early to avoid wasting CPU calling lower() on non-compliant tokens
            if len(word) >= 3 and word.isascii() and word.isalpha():
                # Safe lower-case mapping now that the string is guaranteed pure ASCII (A-Z -> a-z).
                # This sidesteps multi-codepoint Unicode case-folding expansion completely.
                words.add(word.lower())

    return words
