from __future__ import annotations

import threading
import time
from pathlib import Path

import duckdb
import polars as pl
import pyarrow as pa

from analyzer_dataset.domain.data_quality import (
    CORRUPTED_PAYLOAD_MARKER,
    CORRUPTED_PAYLOAD_PATTERN,
)
from analyzer_dataset.domain.tokenizer import (
    ASCII_LOWER,
    ASCII_UPPER,
    CLEAN_PATTERN_DUCKDB,
    WORD_PATTERN_DUCKDB,
)
from analyzer_dataset.repository.vocabulary import (
    load_english_words,
)
from analyzer_dataset.usecase.query import ProgressReporter

ENGINE = "duckdb"


def clean_desc_duckdb(
    desc_expression: str = '"desc"',
) -> str:
    """
    Build the exact native DuckDB production cleaning expression.

    Order:

    1. Remove known corrupted binary payloads.
    2. ASCII lowercase A-Z.
    3. Remove URLs, emails, mentions and hashtags.

    `desc_expression` allows the same production implementation to
    be reused by tests with a different column/expression.
    """
    return f"""
        regexp_replace(
            translate(
                CASE
                    WHEN contains(
                        {desc_expression},
                        '{CORRUPTED_PAYLOAD_MARKER}'
                    )
                    THEN regexp_replace(
                        {desc_expression},
                        '{CORRUPTED_PAYLOAD_PATTERN}',
                        ''
                    )
                    ELSE {desc_expression}
                END,
                '{ASCII_UPPER}',
                '{ASCII_LOWER}'
            ),
            '{CLEAN_PATTERN_DUCKDB}',
            ' ',
            'g'
        )
    """


class DuckDBQuery:
    """
    DuckDB implementation.

    Normal path: a single fused query does tokenization, aggregation
    and top-k/sort in one shot, avoiding intermediate materialization.

    Monitored path: tokenization is split into its own step and
    materialized into a temporary table because query_progress()
    requires a materialization boundary to emit reliable progress
    signals.
    """

    def __init__(
        self,
        parquet_path: Path,
        english_words_path: Path,
        english_stopwords_path: Path,
        min_word_length: int,
        top_k: int,
        threads: int | None,
    ):
        self.parquet_path = parquet_path
        self.english_words_path = english_words_path
        self.english_stopwords_path = english_stopwords_path
        self.min_word_length = min_word_length
        self.top_k = top_k
        self.threads = threads

    @staticmethod
    def _clean_desc_expression() -> str:
        """
        Return the production DuckDB description-cleaning expression.
        """
        return clean_desc_duckdb('"desc"')

    def _build_fused_query(self) -> str:
        """
        Build the single-phase fused query for unmonitored execution.
        """
        parquet_path = str(self.parquet_path)
        cleaned_desc = self._clean_desc_expression()

        return f"""
            WITH tokenized AS (
                SELECT
                    views,
                    regexp_extract_all(
                        {cleaned_desc},
                        '{WORD_PATTERN_DUCKDB}'
                    ) AS words
                FROM read_parquet('{parquet_path}')
                WHERE
                    "desc" IS NOT NULL
                    AND views IS NOT NULL
            ),
            unique_words AS (
                SELECT
                    views,
                    unnest(
                        list_distinct(words)
                    ) AS word
                FROM tokenized
            ),
            english_only AS (
                SELECT
                    u.word,
                    u.views
                FROM unique_words AS u
                SEMI JOIN english_words AS e
                    ON u.word = e.word
            )
            SELECT
                word,
                SUM(views)::UBIGINT AS total_views
            FROM english_only
            GROUP BY word
            ORDER BY total_views DESC
            LIMIT {self.top_k}
        """

    def _build_tokenization_query(self) -> str:
        """
        Build Phase 1 query to materialize intermediate list results
        and track progress.
        """
        parquet_path = str(self.parquet_path)
        cleaned_desc = self._clean_desc_expression()

        return f"""
            CREATE TEMP TABLE tokenized_data AS
            SELECT
                views,
                regexp_extract_all(
                    {cleaned_desc},
                    '{WORD_PATTERN_DUCKDB}'
                ) AS words
            FROM read_parquet('{parquet_path}')
            WHERE
                "desc" IS NOT NULL
                AND views IS NOT NULL
        """

    def _build_aggregation_query(self) -> str:
        """
        Build Phase 2 query to unpack tokens and run global Top-K
        reduction.
        """
        return f"""
            WITH unique_words AS (
                SELECT
                    views,
                    unnest(
                        list_distinct(words)
                    ) AS word
                FROM tokenized_data
            ),
            english_only AS (
                SELECT
                    u.word,
                    u.views
                FROM unique_words AS u
                SEMI JOIN english_words AS e
                    ON u.word = e.word
            )
            SELECT
                word,
                SUM(views)::UBIGINT AS total_views
            FROM english_only
            GROUP BY word
            ORDER BY total_views DESC
            LIMIT {self.top_k}
        """

    @staticmethod
    def _execute_tokenize(
        connection: duckdb.DuckDBPyConnection,
        query: str,
        exception_container: dict[str, BaseException],
    ) -> None:
        try:
            connection.execute(query)
        except BaseException as exc:
            exception_container["exception"] = exc

    def _collect(
        self,
        connection: duckdb.DuckDBPyConnection,
    ) -> pl.DataFrame:
        """
        Single fused query execution without progress overhead.
        """
        return connection.execute(self._build_fused_query()).pl()

    def _collect_monitored(
        self,
        connection: duckdb.DuckDBPyConnection,
        progress: ProgressReporter,
    ) -> pl.DataFrame:
        """
        Two-phase query execution with real-time background progress
        polling.
        """
        connection.execute("SET enable_progress_bar = true")
        connection.execute("SET enable_progress_bar_print = false")

        exception_container: dict[str, BaseException] = {}

        tokenize_thread = threading.Thread(
            target=self._execute_tokenize,
            args=(
                connection,
                self._build_tokenization_query(),
                exception_container,
            ),
            daemon=True,
            name="duckdb-tokenize",
        )

        tokenize_thread.start()

        while tokenize_thread.is_alive():
            percentage = connection.query_progress()

            if percentage >= 0:
                progress.update_percentage(percentage)

            time.sleep(0.2)

        tokenize_thread.join()

        if "exception" in exception_container:
            raise exception_container["exception"]

        progress.update_percentage(99.0)

        result = connection.execute(self._build_aggregation_query()).pl()

        connection.execute("DROP TABLE IF EXISTS tokenized_data")

        progress.update_percentage(100.0)

        return result

    def collect(
        self,
        progress: ProgressReporter | None = None,
    ) -> pl.DataFrame:
        """
        Public entry point to resolve the dataset query using DuckDB.
        """
        connection = duckdb.connect()

        try:
            if self.threads is not None:
                connection.execute(f"SET threads = {self.threads}")

            connection.register(
                "english_words",
                pa.table(
                    {
                        "word": list(
                            load_english_words(
                                self.english_words_path,
                                self.english_stopwords_path,
                                min_word_length=self.min_word_length,
                            )
                        )
                    }
                ),
            )

            if progress is None:
                return self._collect(connection)

            return self._collect_monitored(
                connection,
                progress,
            )

        finally:
            connection.close()


def build_query(
    parquet_path: Path,
    english_words_path: Path,
    english_stopwords_path: Path,
    min_word_length: int,
    top_k: int,
    duckdb_threads: int,
    **_: object,
) -> DuckDBQuery:
    return DuckDBQuery(
        parquet_path=parquet_path,
        english_words_path=english_words_path,
        english_stopwords_path=english_stopwords_path,
        min_word_length=min_word_length,
        top_k=top_k,
        threads=duckdb_threads,
    )
