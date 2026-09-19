from __future__ import annotations

import polars as pl

from tests.fixtures.tokenizer_cases import TokenizerCase
from tiktok_dataset.domain.tokenizer import (
    ASCII_LOWER_MAP,
    CLEAN_PATTERN_POLARS,
    HASHTAG_PATTERN_POLARS,
    MENTION_PATTERN_POLARS,
    WORD_PATTERN,
    EMAIL_PATTERN,
)


def tokenize(text: str) -> tuple[list[str], list[str], list[str], list[str], str]:
    df = pl.DataFrame({"text": [text]})

    hashtags = (
        df.select(
            pl.col("text")
            .str.extract_all(HASHTAG_PATTERN_POLARS)
            .alias("matches")
        )["matches"][0]
        .to_list()
    )

    emails = (
        df.select(
            pl.col("text")
            .str.extract_all(EMAIL_PATTERN)
            .alias("matches")
        )["matches"][0]
        .to_list()
    )

    mentions = (
        df.select(
            pl.col("text")
            .str.replace_all(EMAIL_PATTERN, " ")
            .str.extract_all(MENTION_PATTERN_POLARS)
            .alias("matches")
        )["matches"][0]
        .to_list()
    )

    words = (
        df.with_columns(
            pl.col("text")
            .str.replace_many(ASCII_LOWER_MAP)
            .str.replace_all(CLEAN_PATTERN_POLARS, " ")
            .str.extract_all(WORD_PATTERN)
            .alias("words")
        )["words"][0]
        .to_list()
    )

    tokens = "\x1f".join(sorted(set(words)))

    return hashtags, mentions, emails, words, tokens


def test_polars_tokenizer(tokenizer_case: TokenizerCase) -> None:
    hashtags, mentions, emails, words, tokens = tokenize(tokenizer_case.text)

    assert hashtags == list(tokenizer_case.expected_hashtags), (
        f"{tokenizer_case.name}: hashtag mismatch\n"
        f"text={tokenizer_case.text!r}\n"
        f"expected={tokenizer_case.expected_hashtags!r}\n"
        f"actual={hashtags!r}"
    )

    assert mentions == list(tokenizer_case.expected_mentions), (
        f"{tokenizer_case.name}: mention mismatch\n"
        f"text={tokenizer_case.text!r}\n"
        f"expected={tokenizer_case.expected_mentions!r}\n"
        f"actual={mentions!r}"
    )

    assert words == list(tokenizer_case.expected_words), (
        f"{tokenizer_case.name}: word mismatch\n"
        f"text={tokenizer_case.text!r}\n"
        f"expected={tokenizer_case.expected_words!r}\n"
        f"actual={words!r}"
    )

    assert tokens == tokenizer_case.expected_tokens, (
        f"{tokenizer_case.name}: token mismatch\n"
        f"text={tokenizer_case.text!r}\n"
        f"expected={tokenizer_case.expected_tokens!r}\n"
        f"actual={tokens!r}"
    )