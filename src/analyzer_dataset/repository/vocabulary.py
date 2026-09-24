from __future__ import annotations

from pathlib import Path


def load_english_stopwords(path: Path, min_word_length: int = 3) -> set[str]:
    """
    Load the list of English stop words from a file.
    """
    stop_words: set[str] = set()

    with path.open(
        "r",
        encoding="utf-8",
        errors="ignore",
    ) as file:
        for line in file:
            word = line.strip()

            if len(word) >= min_word_length and word.isascii() and word.isalpha():
                stop_words.add(word.lower())

    return stop_words


def load_english_words(path: Path, stopwords_path: Path, min_word_length: int = 3) -> set[str]:
    """
    Load, filter, and normalize the English vocabulary dictionary.

    Only clean, lower-case, ASCII-only alphabetic tokens are preserved.
    Common stop words are excluded because they are not useful for the
    analytical word-frequency query.
    """
    words: set[str] = set()
    stop_words = load_english_stopwords(stopwords_path, min_word_length=min_word_length)

    with path.open(
        "r",
        encoding="utf-8",
        errors="ignore",
    ) as file:
        for line in file:
            word = line.strip()

            if len(word) >= min_word_length and word.isascii() and word.isalpha():
                word = word.lower()

                if word not in stop_words:
                    words.add(word)

    return words
