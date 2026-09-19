from __future__ import annotations

import argparse
from collections.abc import Generator
from pathlib import Path

import cudf
import duckdb
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from tiktok_dataset.domain.tokenizer import (
    ASCII_LOWER_MAP,
    CLEAN_PATTERN_CUDF,
    CLEAN_PATTERN_DUCKDB,
    CLEAN_PATTERN_POLARS,
    WORD_PATTERN,
    WORD_PATTERN_CUDF,
    WORD_PATTERN_DUCKDB,
)
from tiktok_dataset.repository.vocabulary import load_english_words

PARQUET_PATH = "datasets/videos-00.parquet"

BATCH_SIZE = 5_000_000
MAX_SAVED_EXAMPLES = 5_000
MAX_PRINTED_EXAMPLES = 20

SEPARATOR = "\x1f"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find tokenizer mismatches between Polars, cuDF and DuckDB.")

    parser.add_argument(
        "--vocab",
        type=Path,
        default=None,
        help=("Optional vocabulary file. When provided, only vocabulary words are retained."),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=("Optional output Parquet path. When --vocab is provided, the vocabulary name is included in the output filename."),
    )

    return parser.parse_args()


def get_output_path(
    output: Path | None,
    vocab: Path | None,
) -> Path:
    """Build the output path, including the vocabulary name when provided."""
    if vocab is not None:
        if output is None:
            return Path(f"results/tokenizer_mismatches_{vocab.stem}_filtered.parquet")

        return output.parent / (f"{output.stem}_{vocab.stem}{output.suffix}")

    if output is not None:
        return output

    return Path("results/tokenizer_mismatches.parquet")


def iter_batches_with_row_id(
    path: str,
    batch_size: int,
) -> Generator[pa.Table]:
    """Iterate over the Parquet file in batches with stable row IDs."""
    parquet = pq.ParquetFile(path)
    offset = 0

    for batch in parquet.iter_batches(
        columns=["desc", "views"],
        batch_size=batch_size,
    ):
        table = pa.Table.from_batches([batch])
        row_count = table.num_rows

        row_id = pa.array(
            range(offset, offset + row_count),
            type=pa.int64(),
        )

        offset += row_count

        yield table.append_column("row_id", row_id)


def empty_result() -> pl.DataFrame:
    """Return an empty result with the expected schema."""
    return pl.DataFrame(
        {
            "row_id": pl.Series([], dtype=pl.Int64),
            "views": pl.Series([], dtype=pl.UInt64),
            "desc": pl.Series([], dtype=pl.String),
            "tokens": pl.Series([], dtype=pl.String),
        }
    )


def polars_tokens(
    table: pa.Table,
    language_words: list[str] | None,
) -> pl.DataFrame:
    result = (
        pl.DataFrame(table)
        .lazy()
        .filter(pl.col("desc").is_not_null() & pl.col("views").is_not_null())
        .with_columns(
            pl.col("desc")
            .str.replace_many(ASCII_LOWER_MAP)
            .str.replace_all(CLEAN_PATTERN_POLARS, " ")
            .str.extract_all(WORD_PATTERN)
            .list.unique()
            .alias("words")
        )
    )

    if language_words is not None:
        result = result.with_columns(pl.col("words").list.filter(pl.element().is_in(language_words)).alias("words"))

    return (
        result.with_columns(pl.col("words").list.sort().list.join(SEPARATOR).fill_null("").alias("tokens"))
        .select(
            "row_id",
            "views",
            "desc",
            "tokens",
        )
        .collect()
    )


def cudf_tokens(
    table: pa.Table,
    language_words: cudf.Series | None,
) -> pl.DataFrame:
    """Extract tokens using the cuDF GPU engine."""
    df = cudf.DataFrame.from_arrow(table)
    df = df.dropna(subset=["desc", "views"])

    if len(df) == 0:
        return empty_result()

    desc = (
        df["desc"]
        .str.translate(ASCII_LOWER_MAP)
        .str.replace(
            CLEAN_PATTERN_CUDF,
            " ",
            regex=True,
        )
    )

    words = desc.str.findall(WORD_PATTERN_CUDF).list.unique()

    out = cudf.DataFrame(
        {
            "row_id": df["row_id"],
            "views": df["views"],
            "desc": df["desc"],
            "words": words,
        }
    )

    out = out.explode("words", ignore_index=True).dropna(subset=["words"])

    if len(out) == 0:
        return empty_result()

    if language_words is not None:
        out = out[out["words"].isin(language_words)]

        if len(out) == 0:
            return empty_result()

    pdf = pl.DataFrame(out.to_arrow())

    return (
        pdf.group_by(
            "row_id",
            "views",
            "desc",
        )
        .agg(pl.col("words").unique().sort().str.join(SEPARATOR).alias("tokens"))
        .select(
            "row_id",
            "views",
            "desc",
            "tokens",
        )
    )


def duckdb_tokens(
    con: duckdb.DuckDBPyConnection,
    table: pa.Table,
    has_vocabulary: bool,
) -> pl.DataFrame:
    """Extract tokens using the DuckDB engine."""
    con.register("batch", table)

    try:
        if has_vocabulary:
            query = f"""
                WITH tokenized AS (
                    SELECT
                        row_id,
                        views,
                        "desc",
                        list_distinct(
                            regexp_extract_all(
                                regexp_replace(
                                    translate(
                                        "desc",
                                        'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                                        'abcdefghijklmnopqrstuvwxyz'
                                    ),
                                    '{CLEAN_PATTERN_DUCKDB}',
                                    ' ',
                                    'g'
                                ),
                                '{WORD_PATTERN_DUCKDB}'
                            )
                        ) AS words
                    FROM batch
                    WHERE "desc" IS NOT NULL
                      AND views IS NOT NULL
                ),
                english_only AS (
                    SELECT
                        t.row_id,
                        t.views,
                        t."desc",
                        u.word
                    FROM tokenized AS t
                    CROSS JOIN LATERAL unnest(t.words) AS u(word)
                    SEMI JOIN language_words AS l
                        ON u.word = l.word
                ),
                grouped AS (
                    SELECT
                        row_id,
                        views,
                        "desc",
                        list_sort(
                            list_distinct(list(word))
                        ) AS words
                    FROM english_only
                    GROUP BY
                        row_id,
                        views,
                        "desc"
                )
                SELECT
                    row_id,
                    views,
                    "desc",
                    array_to_string(words, chr(31)) AS tokens
                FROM grouped
            """
        else:
            query = f"""
                SELECT
                    row_id,
                    views,
                    "desc",
                    array_to_string(
                        list_sort(
                            list_distinct(
                                regexp_extract_all(
                                    regexp_replace(
                                        translate(
                                            "desc",
                                            'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                                            'abcdefghijklmnopqrstuvwxyz'
                                        ),
                                        '{CLEAN_PATTERN_DUCKDB}',
                                        ' ',
                                        'g'
                                    ),
                                    '{WORD_PATTERN_DUCKDB}'
                                )
                            )
                        ),
                        chr(31)
                    ) AS tokens
                FROM batch
                WHERE "desc" IS NOT NULL
                  AND views IS NOT NULL
            """

        return con.execute(query).pl()

    finally:
        con.unregister("batch")


def combine_and_flag(
    polars_result: pl.DataFrame,
    cudf_result: pl.DataFrame,
    duckdb_result: pl.DataFrame,
) -> pl.DataFrame:
    """Align engine outputs and isolate tokenizer differences."""
    combined = (
        polars_result.rename({"tokens": "tokens_polars"})
        .join(
            cudf_result.select(
                "row_id",
                pl.col("tokens").alias("tokens_cudf"),
            ),
            on="row_id",
            how="left",
        )
        .join(
            duckdb_result.select(
                "row_id",
                pl.col("tokens").alias("tokens_duckdb"),
            ),
            on="row_id",
            how="left",
        )
        .with_columns(
            pl.col("tokens_polars").fill_null("").alias("tokens_polars"),
            pl.col("tokens_cudf").fill_null("").alias("tokens_cudf"),
            pl.col("tokens_duckdb").fill_null("").alias("tokens_duckdb"),
        )
    )

    return combined.with_columns(
        (pl.col("tokens_polars") != pl.col("tokens_cudf")).alias("cudf_vs_polars"),
        (pl.col("tokens_polars") != pl.col("tokens_duckdb")).alias("duckdb_vs_polars"),
        (pl.col("tokens_duckdb") != pl.col("tokens_cudf")).alias("duckdb_vs_cudf"),
    ).filter(pl.col("cudf_vs_polars") | pl.col("duckdb_vs_polars") | pl.col("duckdb_vs_cudf"))


def load_vocabulary(
    vocab_path: Path | None,
) -> tuple[list[str] | None, cudf.Series | None]:
    if vocab_path is None:
        print("global mode: no vocabulary filtering")
        return None, None

    if not vocab_path.exists():
        raise FileNotFoundError(f"Vocabulary file does not exist: {vocab_path}")

    words = sorted(set(load_english_words(vocab_path)))
    words_cudf = cudf.Series(words)

    print(f"target vocabulary: {len(words):,} words")
    print(f"vocabulary path: {vocab_path}")

    return words, words_cudf


def process_batch(
    con: duckdb.DuckDBPyConnection,
    table: pa.Table,
    language_words: list[str] | None,
    language_words_cudf: cudf.Series | None,
) -> pl.DataFrame:
    polars_result = polars_tokens(
        table,
        language_words,
    )

    cudf_result = cudf_tokens(
        table,
        language_words_cudf,
    )

    duckdb_result = duckdb_tokens(
        con,
        table,
        has_vocabulary=language_words is not None,
    )

    return combine_and_flag(
        polars_result,
        cudf_result,
        duckdb_result,
    )


def save_results(
    saved_frames: list[pl.DataFrame],
    output_path: Path,
) -> None:
    if not saved_frames:
        return

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result = pl.concat(
        saved_frames,
        how="vertical",
    )

    if output_path.suffix == ".csv":
        result.write_csv(output_path)
    elif output_path.suffix == ".parquet":
        result.write_parquet(output_path)
    else:
        raise ValueError(f"Unsupported output format: {output_path.suffix}")

    print()
    print(f"saved {len(result):,} mismatch examples to {output_path}")


def main() -> None:
    args = parse_args()

    output_path = get_output_path(
        args.output,
        args.vocab,
    )

    language_words, language_words_cudf = load_vocabulary(
        args.vocab,
    )

    seen_desc: set[str] = set()
    saved_frames: list[pl.DataFrame] = []

    printed = 0
    total_rows = 0
    total_mismatched_rows = 0

    pair_totals = {
        "cudf_vs_polars": 0,
        "duckdb_vs_polars": 0,
        "duckdb_vs_cudf": 0,
    }

    con = duckdb.connect()

    try:
        if language_words is not None:
            con.register(
                "language_words",
                pa.Table.from_pydict({"word": language_words}),
            )

        for batch_index, table in enumerate(
            iter_batches_with_row_id(
                PARQUET_PATH,
                BATCH_SIZE,
            ),
            start=1,
        ):
            total_rows += table.num_rows

            mismatches = process_batch(
                con,
                table,
                language_words,
                language_words_cudf,
            )

            total_mismatched_rows += len(mismatches)

            for pair in pair_totals:
                pair_totals[pair] += int(mismatches[pair].sum())

            if len(seen_desc) < MAX_SAVED_EXAMPLES and not mismatches.is_empty():
                new_rows = (
                    mismatches.filter(~pl.col("desc").is_in(seen_desc))
                    .unique(
                        subset=["desc"],
                        keep="first",
                    )
                    .head(MAX_SAVED_EXAMPLES - len(seen_desc))
                )

                if not new_rows.is_empty():
                    seen_desc.update(new_rows["desc"].to_list())
                    saved_frames.append(new_rows)

                    if printed < MAX_PRINTED_EXAMPLES:
                        for row in new_rows.head(MAX_PRINTED_EXAMPLES - printed).iter_rows(named=True):
                            pairs = [pair for pair in pair_totals if row[pair]]

                            print()
                            print(f"row_id: {row['row_id']} views: {row['views']}")
                            print(f"mismatched: {pairs}")
                            print(f"desc: {row['desc']!r}")
                            print(f"polars: {row['tokens_polars']!r}")
                            print(f"cudf:   {row['tokens_cudf']!r}")
                            print(f"duckdb: {row['tokens_duckdb']!r}")

                            printed += 1

                            if printed >= MAX_PRINTED_EXAMPLES:
                                break

            print(
                f"batch {batch_index}: "
                f"{table.num_rows:,} rows "
                f"(total {total_rows:,}) | "
                f"mismatched rows: "
                f"{total_mismatched_rows:,} | "
                f"cuDF/Polars="
                f"{pair_totals['cudf_vs_polars']:,} "
                f"DuckDB/Polars="
                f"{pair_totals['duckdb_vs_polars']:,} "
                f"DuckDB/cuDF="
                f"{pair_totals['duckdb_vs_cudf']:,}",
                flush=True,
            )

    finally:
        con.close()

    print()
    print("=== SUMMARY ===")
    print(f"total rows scanned: {total_rows:,}")
    print(f"total mismatched rows: {total_mismatched_rows:,}")
    print(f"cuDF/Polars: {pair_totals['cudf_vs_polars']:,}")
    print(f"DuckDB/Polars: {pair_totals['duckdb_vs_polars']:,}")
    print(f"DuckDB/cuDF: {pair_totals['duckdb_vs_cudf']:,}")

    save_results(
        saved_frames,
        output_path,
    )


if __name__ == "__main__":
    main()
