from __future__ import annotations

import threading
import time
from pathlib import Path

import duckdb
import polars as pl
import pyarrow as pa

from tiktok_dataset.domain.tokenizer import (
    CLEAN_PATTERN,
    WORD_PATTERN,
)
from tiktok_dataset.repository.vocabulary import (
    load_english_words,
)
from tiktok_dataset.usecase.query import ProgressReporter

ENGINE = "duckdb"


class DuckDBQuery:
    """
    DuckDB implementation.

    Normal path: a single fused query does
    tokenization, aggregation and top-k/sort in one shot, no
    intermediate materialization.

    Monitored path: tokenization is split into its own step,
    materialized into a temp table, because `query_progress()`
    is only a reliable signal for that step, it's a plain
    scan/filter/regex query with no row-count-changing operators.
    The `unnest` + semi-join + `group by` step that follows has a
    cardinality-estimation blind spot around `unnest`, so its
    progress isn't tracked; it's relatively short compared to the tokenization step.
    """

    def __init__(
        self,
        parquet_path: Path,
        english_words_path: Path,
        top_k: int,
        threads: int | None,
    ):
        self.parquet_path = parquet_path
        self.english_words_path = english_words_path
        self.top_k = top_k
        self.threads = threads

    def _build_fused_query(self) -> str:
        parquet_path = str(self.parquet_path)
        return f"""
            WITH tokenized AS (
                SELECT
                    views,
                    regexp_extract_all(
                        regexp_replace(
                            lower("desc"),
                            '{CLEAN_PATTERN}',
                            ' ',
                            'g'
                        ),
                        '{WORD_PATTERN}'
                    ) AS words
                FROM read_parquet('{parquet_path}')
                WHERE "desc" IS NOT NULL AND views IS NOT NULL
            ),
            unique_words AS (
                SELECT
                    views,
                    unnest(list_distinct(words)) AS word
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
        parquet_path = str(self.parquet_path)
        return f"""
            CREATE TEMP TABLE tokenized_data AS
            SELECT
                views,
                regexp_extract_all(
                    regexp_replace(
                        lower("desc"),
                        '{CLEAN_PATTERN}',
                        ' ',
                        'g'
                    ),
                    '{WORD_PATTERN}'
                ) AS words
            FROM read_parquet('{parquet_path}')
            WHERE "desc" IS NOT NULL AND views IS NOT NULL;
        """

    def _build_aggregation_query(self) -> str:
        return f"""
            WITH unique_words AS (
                SELECT
                    views,
                    unnest(list_distinct(words)) AS word
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
        """Single fused query: no materialization, no progress tracking."""
        return connection.execute(self._build_fused_query()).pl()

    def _collect_monitored(
        self,
        connection: duckdb.DuckDBPyConnection,
        progress: ProgressReporter,
    ) -> pl.DataFrame:
        """
        Two-phase: tokenization is tracked via `query_progress()`
        (reliable here, since this query has no row-count-changing
        operators); aggregation is fast by comparison and its
        progress isn't reliably trackable, so it's reported as one
        jump to completion.
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
        connection = duckdb.connect()

        try:
            if self.threads is not None:
                connection.execute(f"SET threads = {self.threads}")

            connection.register(
                "english_words",
                pa.table({"word": list(load_english_words(self.english_words_path))}),
            )

            if progress is None:
                return self._collect(connection)

            return self._collect_monitored(connection, progress)

        finally:
            connection.close()


def build_query(
    parquet_path: Path,
    english_words_path: Path,
    top_k: int,
    duckdb_threads: int | None,
    **_: object,
) -> DuckDBQuery:
    return DuckDBQuery(
        parquet_path=parquet_path,
        english_words_path=english_words_path,
        top_k=top_k,
        threads=duckdb_threads,
    )
