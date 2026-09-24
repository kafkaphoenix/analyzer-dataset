from __future__ import annotations

import cudf

from tests.scenarios.tokenizer_cases import (
    TokenizerCase,
    strip_trailing_url_punctuation,
    strip_leading_url_boundary,
)
from tiktok_dataset.domain.tokenizer import (
    BARE_DOMAIN_PATTERN,
    EMAIL_PATTERN,
    HASHTAG_PATTERN_CUDF,
    MENTION_PATTERN_CUDF,
    URL_PATTERN,
    URL_SCHEME_PATTERN,
    WORD_PATTERN_CUDF,
)
from tiktok_dataset.repository.engines.cudf import clean_desc_cudf_fast


def tokenize(
    text: str,
) -> tuple[list[str], list[str], list[str], list[str], str, list[str]]:
    df = cudf.DataFrame({"text": [text]})

    source = df["text"]

    # URLs.
    urls = source.str.findall(
        URL_PATTERN,
    ).iloc[0]

    urls = (
        [
            strip_trailing_url_punctuation(
                strip_leading_url_boundary(url)
            )
            for url in urls
        ]
        if urls is not None
        else []
    )

    # URL scheme.
    source = source.str.replace(
        URL_SCHEME_PATTERN,
        " ",
        regex=True,
    )

    # Bare domains.
    source = source.str.replace(
        BARE_DOMAIN_PATTERN,
        " ",
        regex=True,
    )

    # Emails.
    emails = source.str.findall(
        EMAIL_PATTERN,
    ).iloc[0]

    emails = list(emails) if emails is not None else []

    source = source.str.replace(
        EMAIL_PATTERN,
        " ",
        regex=True,
    )

    # Mentions.
    mentions = source.str.findall(
        MENTION_PATTERN_CUDF,
    ).iloc[0]

    mentions = list(mentions) if mentions is not None else []

    source = source.str.replace(
        MENTION_PATTERN_CUDF,
        " ",
        regex=True,
    )

    # Hashtags.
    hashtags = source.str.findall(
        HASHTAG_PATTERN_CUDF,
    ).iloc[0]

    hashtags = list(hashtags) if hashtags is not None else []

    source = source.str.replace(
        HASHTAG_PATTERN_CUDF,
        " ",
        regex=True,
    )

    # Words come directly from the real production implementation.
    cleaned = clean_desc_cudf_fast(
        df["text"],
    )

    words = cleaned.str.findall(
        WORD_PATTERN_CUDF,
    ).iloc[0]

    words = list(words) if words is not None else []

    tokens = "\x1f".join(
        sorted(set(words)),
    )

    return (
        hashtags,
        mentions,
        emails,
        words,
        tokens,
        urls,
    )


def test_cudf_tokenizer(
    tokenizer_case: TokenizerCase,
) -> None:
    (
        hashtags,
        mentions,
        emails,
        words,
        tokens,
        urls,
    ) = tokenize(
        tokenizer_case.text,
    )

    assert hashtags == list(
        tokenizer_case.expected_hashtags,
    ), (
        f"{tokenizer_case.name}: hashtag mismatch\n"
        f"text={tokenizer_case.text!r}\n"
        f"expected={tokenizer_case.expected_hashtags!r}\n"
        f"actual={hashtags!r}"
    )

    assert mentions == list(
        tokenizer_case.expected_mentions,
    ), (
        f"{tokenizer_case.name}: mention mismatch\n"
        f"text={tokenizer_case.text!r}\n"
        f"expected={tokenizer_case.expected_mentions!r}\n"
        f"actual={mentions!r}"
    )

    assert emails == list(
        tokenizer_case.expected_emails,
    ), (
        f"{tokenizer_case.name}: email mismatch\n"
        f"text={tokenizer_case.text!r}\n"
        f"expected={tokenizer_case.expected_emails!r}\n"
        f"actual={emails!r}"
    )

    assert words == list(
        tokenizer_case.expected_words,
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
        tokenizer_case.expected_urls,
    ), (
        f"{tokenizer_case.name}: url mismatch\n"
        f"text={tokenizer_case.text!r}\n"
        f"expected={tokenizer_case.expected_urls!r}\n"
        f"actual={urls!r}"
    )