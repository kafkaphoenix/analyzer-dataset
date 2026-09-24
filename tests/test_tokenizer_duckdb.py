from __future__ import annotations

import duckdb

from tests.scenarios.tokenizer_cases import TokenizerCase, strip_trailing_url_punctuation, strip_leading_url_boundary
from analyzer_dataset.domain.tokenizer import (
    EMAIL_PATTERN,
    HASHTAG_PATTERN_DUCKDB,
    MENTION_PATTERN_DUCKDB,
    URL_PATTERN,
    WORD_PATTERN_DUCKDB,
)
from analyzer_dataset.repository.engines.duckdb import (
    clean_desc_duckdb,
)


def tokenize(
    text: str,
) -> tuple[list[str], list[str], list[str], list[str], str, list[str]]:
    con = duckdb.connect()

    try:
        # 1. Extract emails from the original text.
        email_query = f"""
            SELECT regexp_extract_all(
                ?,
                '{EMAIL_PATTERN}'
            )
        """

        emails = con.execute(
            email_query,
            [text],
        ).fetchone()[0]

        emails = list(strip_trailing_url_punctuation(strip_leading_url_boundary(email)) for email in emails)

        # 2. Remove emails before extracting URLs.
        #
        # Email precedence is intentional. An @ inside a valid email
        # address must not interfere with the email match.
        url_query = f"""
            SELECT regexp_extract_all(
                regexp_replace(
                    ?,
                    '{EMAIL_PATTERN}',
                    ' ',
                    'g'
                ),
                '{URL_PATTERN}'
            )
        """

        urls = con.execute(
            url_query,
            [text],
        ).fetchone()[0]

        urls = list(strip_trailing_url_punctuation(strip_leading_url_boundary(url)) for url in urls)

        # 3. Remove emails and URLs before extracting mentions.
        #
        # This prevents @ inside URLs and email addresses from being
        # interpreted as mentions.
        mention_query = f"""
            SELECT regexp_extract_all(
                regexp_replace(
                    regexp_replace(
                        ?,
                        '{EMAIL_PATTERN}',
                        ' ',
                        'g'
                    ),
                    '{URL_PATTERN}',
                    ' ',
                    'g'
                ),
                '{MENTION_PATTERN_DUCKDB}'
            )
        """

        mentions = con.execute(
            mention_query,
            [text],
        ).fetchone()[0]

        mentions = list(mentions)

        # 4. Remove emails, URLs and mentions before extracting hashtags.
        #
        # This prevents # inside URLs and already-consumed structures
        # from being interpreted as hashtags.
        hashtag_query = f"""
            SELECT regexp_extract_all(
                regexp_replace(
                    regexp_replace(
                        regexp_replace(
                            ?,
                            '{EMAIL_PATTERN}',
                            ' ',
                            'g'
                        ),
                        '{URL_PATTERN}',
                        ' ',
                        'g'
                    ),
                    '{MENTION_PATTERN_DUCKDB}',
                    ' ',
                    'g'
                ),
                '{HASHTAG_PATTERN_DUCKDB}'
            )
        """

        hashtags = con.execute(
            hashtag_query,
            [text],
        ).fetchone()[0]

        hashtags = list(hashtags)

        # 5. Use the exact production DuckDB cleaning implementation
        # for word tokenization.
        cleaned_desc = clean_desc_duckdb(
            '"text"'
        )

        query = f"""
            SELECT
                regexp_extract_all(
                    {cleaned_desc},
                    '{WORD_PATTERN_DUCKDB}'
                ) AS words
            FROM (
                SELECT ? AS text
            )
        """

        words = con.execute(
            query,
            [text],
        ).fetchone()[0]

        words = list(words)

        # 6. Build unique token string.
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

    finally:
        con.close()


def test_duckdb_tokenizer(
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
