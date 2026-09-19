from __future__ import annotations

import cudf

from tests.fixtures.tokenizer_cases import TokenizerCase
from tiktok_dataset.domain.tokenizer import (
    ASCII_LOWER_MAP,
    CLEAN_PATTERN_CUDF,
    HASHTAG_PATTERN_CUDF,
    MENTION_PATTERN_CUDF,
    WORD_PATTERN_CUDF,
    EMAIL_PATTERN,
)


def tokenize(text: str) -> tuple[list[str], list[str], list[str], list[str], str]:
    df = cudf.DataFrame({"text": [text]})

    hashtags = df["text"].str.findall(
        HASHTAG_PATTERN_CUDF,
    ).iloc[0]

    if hashtags is None:
        hashtags = []

    hashtags = list(hashtags)

    emails = df["text"].str.findall(
        EMAIL_PATTERN,
    ).iloc[0]

    if emails is None:
        emails = []

    emails = list(emails)

    mention_source = df["text"].str.replace(
        EMAIL_PATTERN,
        " ",
        regex=True,
    )

    mentions = mention_source.str.findall(
        MENTION_PATTERN_CUDF,
    ).iloc[0]

    if mentions is None:
        mentions = []

    mentions = list(mentions)

    cleaned = (
        df["text"]
        .str.translate(ASCII_LOWER_MAP)
        .str.replace(
            CLEAN_PATTERN_CUDF,
            " ",
            regex=True,
        )
    )

    words = cleaned.str.findall(
        WORD_PATTERN_CUDF,
    ).iloc[0]

    if words is None:
        words = []

    words = list(words)

    tokens = "\x1f".join(sorted(set(words)))

    return hashtags, mentions, emails, words, tokens


def test_cudf_tokenizer(tokenizer_case: TokenizerCase) -> None:
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

    assert emails == list(tokenizer_case.expected_emails), (
        f"{tokenizer_case.name}: email mismatch\n"
        f"text={tokenizer_case.text!r}\n"
        f"expected={tokenizer_case.expected_emails!r}\n"
        f"actual={emails!r}"
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