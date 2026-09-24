from __future__ import annotations

import polars as pl

from tests.scenarios.tokenizer_cases import TokenizerCase, strip_trailing_url_punctuation, strip_leading_url_boundary
from analyzer_dataset.domain.tokenizer import (
    EMAIL_PATTERN,
    HASHTAG_PATTERN_POLARS,
    MENTION_PATTERN_POLARS,
    URL_PATTERN,
    WORD_PATTERN_POLARS,
)
from analyzer_dataset.repository.engines.polars_common import clean_desc_polars


def tokenize(
    text: str,
) -> tuple[list[str], list[str], list[str], list[str], str, list[str]]:
    df = pl.DataFrame({"text": [text]})

    # 1. Extract emails from the original text.
    emails = (
        df.select(
            pl.col("text")
            .str.extract_all(EMAIL_PATTERN)
            .alias("matches")
        )["matches"][0]
        .to_list()
    )

    emails = list(strip_trailing_url_punctuation(strip_leading_url_boundary(email)) for email in emails)

    # 2. Extract URLs after removing emails.
    #
    # This keeps email precedence: an email is treated as an email even
    # when it occurs in text that otherwise contains URL-like content.
    url_source = (
        pl.col("text")
        .str.replace_all(EMAIL_PATTERN, " ")
    )

    # URLs are not currently returned by this helper, but removing them
    # before mention/hashtag extraction prevents @ and # inside URLs
    # from being interpreted as separate structures.
    url_clean_source = (
        url_source
        .str.replace_all(URL_PATTERN, " ")
    )

    urls = (
        df.select(
            url_source
            .str.extract_all(URL_PATTERN)
            .alias("matches")
        )["matches"][0]
        .to_list()
    )
    urls = list(strip_trailing_url_punctuation(strip_leading_url_boundary(url)) for url in urls)

    # 3. Extract mentions after removing emails and URLs.
    mentions = (
        df.select(
            url_clean_source
            .str.extract_all(MENTION_PATTERN_POLARS)
            .alias("matches")
        )["matches"][0]
        .to_list()
    )

    # 4. Extract hashtags after removing emails, URLs and mentions.
    hashtag_source = (
        url_clean_source
        .str.replace_all(MENTION_PATTERN_POLARS, " ")
    )

    hashtags = (
        df.select(
            hashtag_source
            .str.extract_all(HASHTAG_PATTERN_POLARS)
            .alias("matches")
        )["matches"][0]
        .to_list()
    )

    # 5. Extract words using the production cleanup pipeline.
    words = (
        df.select(
            clean_desc_polars(
                pl.col("text")
            )
            .str.extract_all(WORD_PATTERN_POLARS)
            .alias("words")
        )["words"][0]
        .to_list()
    )

    tokens = "\x1f".join(
        sorted(set(words))
    )

    return (
        hashtags,
        mentions,
        emails,
        words,
        tokens,
        urls,
    )


def test_polars_tokenizer(
    tokenizer_case: TokenizerCase,
) -> None:
    hashtags, mentions, emails, words, tokens, urls = tokenize(
        tokenizer_case.text
    )

    assert hashtags == list(
        tokenizer_case.expected_hashtags
    ), (
        f"{tokenizer_case.name}: hashtag mismatch\n"
        f"text={tokenizer_case.text!r}\n"
        f"expected={tokenizer_case.expected_hashtags!r}\n"
        f"actual={hashtags!r}"
    )

    assert mentions == list(
        tokenizer_case.expected_mentions
    ), (
        f"{tokenizer_case.name}: mention mismatch\n"
        f"text={tokenizer_case.text!r}\n"
        f"expected={tokenizer_case.expected_mentions!r}\n"
        f"actual={mentions!r}"
    )

    assert emails == list(
        tokenizer_case.expected_emails
    ), (
        f"{tokenizer_case.name}: email mismatch\n"
        f"text={tokenizer_case.text!r}\n"
        f"expected={tokenizer_case.expected_emails!r}\n"
        f"actual={emails!r}"
    )

    assert words == list(
        tokenizer_case.expected_words
    ), (
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

    assert urls == list(
        tokenizer_case.expected_urls
    ), (
        f"{tokenizer_case.name}: url mismatch\n"
        f"text={tokenizer_case.text!r}\n"
        f"expected={tokenizer_case.expected_urls!r}\n"
        f"actual={urls!r}"
    )