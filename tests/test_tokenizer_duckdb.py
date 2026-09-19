from __future__ import annotations

import duckdb

from tests.fixtures.tokenizer_cases import TokenizerCase
from tiktok_dataset.domain.tokenizer import (
    CLEAN_PATTERN_DUCKDB,
    HASHTAG_PATTERN_DUCKDB,
    MENTION_PATTERN_DUCKDB,
    WORD_PATTERN_DUCKDB,
    EMAIL_PATTERN,
)


def tokenize(text: str) -> tuple[list[str], list[str], list[str], list[str], str]:
    con = duckdb.connect()

    try:
        query = f"""
            WITH cleaned AS (
                SELECT
                    regexp_replace(
                        translate(
                            text,
                            'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                            'abcdefghijklmnopqrstuvwxyz'
                        ),
                        '{CLEAN_PATTERN_DUCKDB}',
                        ' ',
                        'g'
                    ) AS text
                FROM (
                    SELECT ? AS text
                )
            )
            SELECT
                regexp_extract_all(
                    text,
                    '{WORD_PATTERN_DUCKDB}'
                ) AS words
            FROM cleaned
        """

        words = con.execute(
            query,
            [text],
        ).fetchone()[0]
        words = list(words)

        hashtag_query = f"""
            SELECT regexp_extract_all(
                ?,
                '{HASHTAG_PATTERN_DUCKDB}'
            )
        """

        hashtags = con.execute(
            hashtag_query,
            [text],
        ).fetchone()[0]
        hashtags = list(hashtags)

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
        emails = list(emails)

        mention_query = f"""
            SELECT regexp_extract_all(
                regexp_replace(
                    ?,
                    '{EMAIL_PATTERN}',
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

        tokens = "\x1f".join(sorted(set(words)))

        return hashtags, mentions, emails, words, tokens

    finally:
        con.close()

def test_duckdb_tokenizer(tokenizer_case: TokenizerCase) -> None:
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