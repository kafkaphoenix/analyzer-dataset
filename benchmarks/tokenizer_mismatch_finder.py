from __future__ import annotations

import argparse
from collections.abc import Generator
from pathlib import Path

import cudf
import duckdb
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from tiktok_dataset.domain.data_quality import (
    CORRUPTED_PAYLOAD_MARKER,
)
from tiktok_dataset.domain.tokenizer import (
    WORD_PATTERN_CUDF,
    WORD_PATTERN_DUCKDB,
    WORD_PATTERN_POLARS,
)
from tiktok_dataset.repository.engines.cudf import (
    clean_desc_cudf_fast,
)
from tiktok_dataset.repository.engines.duckdb import (
    clean_desc_duckdb,
)
from tiktok_dataset.repository.engines.polars_common import (
    clean_desc_polars,
)
from tiktok_dataset.repository.vocabulary import (
    load_english_words,
)

PARQUET_PATH = "datasets/videos-00.parquet"

BATCH_SIZE = 5_000_000

MAX_SAVED_EXAMPLES = 5_000
MAX_PRINTED_EXAMPLES = 20

SEPARATOR = "\x1f"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Compare tokenizer output between Polars, cuDF and DuckDB, or attribute per-word aggregation differences.")
    )

    parser.add_argument(
        "--vocab",
        type=Path,
        default=None,
        help="Optional vocabulary file.",
    )

    parser.add_argument(
        "--stopwords",
        type=Path,
        default=None,
        help="Optional stopwords file.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output Parquet/CSV path.",
    )

    parser.add_argument(
        "--word",
        type=str,
        default=None,
        help=("Analyze one specific word across the full dataset. For example: --word love"),
    )

    return parser.parse_args()


def get_output_path(
    output: Path | None,
    vocab: Path | None,
) -> Path:
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
        columns=[
            "desc",
            "views",
        ],
        batch_size=batch_size,
    ):
        table = pa.Table.from_batches([batch])

        row_count = table.num_rows

        row_id = pa.array(
            range(
                offset,
                offset + row_count,
            ),
            type=pa.int64(),
        )

        offset += row_count

        yield table.append_column(
            "row_id",
            row_id,
        )


def empty_result() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "row_id": pl.Series(
                [],
                dtype=pl.Int64,
            ),
            "views": pl.Series(
                [],
                dtype=pl.UInt64,
            ),
            "desc": pl.Series(
                [],
                dtype=pl.String,
            ),
            "tokens": pl.Series(
                [],
                dtype=pl.String,
            ),
        }
    )


def polars_tokens(
    table: pa.Table,
    language_words: list[str] | None,
) -> pl.DataFrame:
    """
    Extract tokens using the exact production Polars cleaning pipeline.
    """
    result = (
        pl.DataFrame(table)
        .lazy()
        .filter(pl.col("desc").is_not_null() & pl.col("views").is_not_null())
        .with_columns(
            clean_desc_polars(
                pl.col("desc"),
            )
            .str.extract_all(
                WORD_PATTERN_POLARS,
            )
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
    """
    Extract tokens using the exact production cuDF cleaning pipeline.
    """
    df = cudf.DataFrame.from_arrow(table)

    df = df.dropna(
        subset=[
            "desc",
            "views",
        ]
    )

    if len(df) == 0:
        return empty_result()

    desc = clean_desc_cudf_fast(df["desc"])

    words = desc.str.findall(WORD_PATTERN_CUDF).list.unique()

    out = cudf.DataFrame(
        {
            "row_id": df["row_id"],
            "views": df["views"],
            "desc": df["desc"],
            "words": words,
        }
    )

    out = out.explode(
        "words",
        ignore_index=True,
    ).dropna(subset=["words"])

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
    """
    Extract tokens using the exact production DuckDB cleaning pipeline.
    """
    con.register(
        "batch",
        table,
    )

    cleaned_desc = clean_desc_duckdb('"desc"')

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
                                {cleaned_desc},
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
                    CROSS JOIN LATERAL
                        unnest(t.words) AS u(word)
                    SEMI JOIN language_words AS l
                        ON u.word = l.word
                ),
                grouped AS (
                    SELECT
                        row_id,
                        views,
                        "desc",
                        list_sort(
                            list_distinct(
                                list(word)
                            )
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
                    array_to_string(
                        words,
                        chr(31)
                    ) AS tokens
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
                                    {cleaned_desc},
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
        .filter(
            ~pl.col("desc").str.contains(
                CORRUPTED_PAYLOAD_MARKER,
                literal=True,
            )
        )
    )

    return combined.with_columns(
        (pl.col("tokens_polars") != pl.col("tokens_cudf")).alias("cudf_vs_polars"),
        (pl.col("tokens_polars") != pl.col("tokens_duckdb")).alias("duckdb_vs_polars"),
        (pl.col("tokens_duckdb") != pl.col("tokens_cudf")).alias("duckdb_vs_cudf"),
    ).filter(pl.col("cudf_vs_polars") | pl.col("duckdb_vs_polars") | pl.col("duckdb_vs_cudf"))


def load_vocabulary(
    vocab_path: Path | None,
    stopwords_path: Path | None,
) -> tuple[
    list[str] | None,
    cudf.Series | None,
]:
    if vocab_path is None:
        print("global mode: no vocabulary filtering")
        return None, None

    if not vocab_path.exists():
        raise FileNotFoundError(f"Vocabulary file does not exist: {vocab_path}")

    words = sorted(
        set(
            load_english_words(
                vocab_path,
                stopwords_path,
            )
        )
    )

    words_cudf = cudf.Series(words)

    print(f"target vocabulary: {len(words):,} words")
    print(f"vocabulary path: {vocab_path}")
    print(f"stopwords path: {stopwords_path}")

    return words, words_cudf


def find_word_rows_polars(
    table: pa.Table,
    word: str,
) -> pl.DataFrame:
    """
    Find rows containing a word using the exact production Polars
    cleaning pipeline.
    """
    result = (
        pl.DataFrame(table)
        .lazy()
        .filter(pl.col("desc").is_not_null() & pl.col("views").is_not_null())
        .with_columns(
            clean_desc_polars(
                pl.col("desc"),
            )
            .str.extract_all(
                WORD_PATTERN_POLARS,
            )
            .list.unique()
            .alias("words")
        )
        .filter(pl.col("words").list.contains(word))
        .select(
            "row_id",
            "views",
            "desc",
        )
    )

    return result.collect()


def find_word_rows_cudf(
    table: pa.Table,
    word: str,
) -> pl.DataFrame:
    """
    Find rows containing a word using the exact production cuDF
    cleaning pipeline.
    """
    df = cudf.DataFrame.from_arrow(table)

    df = df.dropna(
        subset=[
            "desc",
            "views",
        ]
    )

    if len(df) == 0:
        return pl.DataFrame(
            {
                "row_id": pl.Series(
                    [],
                    dtype=pl.Int64,
                ),
                "views": pl.Series(
                    [],
                    dtype=pl.UInt64,
                ),
                "desc": pl.Series(
                    [],
                    dtype=pl.String,
                ),
            }
        )

    desc = clean_desc_cudf_fast(df["desc"])

    words = desc.str.findall(WORD_PATTERN_CUDF).list.unique()

    mask = words.list.contains(word)

    result = cudf.DataFrame(
        {
            "row_id": df["row_id"],
            "views": df["views"],
            "desc": df["desc"],
        }
    )

    result = result[mask]

    if len(result) == 0:
        return pl.DataFrame(
            {
                "row_id": pl.Series(
                    [],
                    dtype=pl.Int64,
                ),
                "views": pl.Series(
                    [],
                    dtype=pl.UInt64,
                ),
                "desc": pl.Series(
                    [],
                    dtype=pl.String,
                ),
            }
        )

    return pl.DataFrame(result.to_arrow())


def find_word_rows_duckdb(
    con: duckdb.DuckDBPyConnection,
    table: pa.Table,
    word: str,
) -> pl.DataFrame:
    """
    Find rows containing a word using the exact production DuckDB
    cleaning pipeline.
    """
    con.register(
        "batch",
        table,
    )

    try:
        escaped_word = word.replace(
            "'",
            "''",
        )

        cleaned_desc = clean_desc_duckdb('"desc"')

        query = f"""
            WITH tokenized AS (
                SELECT
                    row_id,
                    views,
                    "desc",
                    list_distinct(
                        regexp_extract_all(
                            {cleaned_desc},
                            '{WORD_PATTERN_DUCKDB}'
                        )
                    ) AS words
                FROM batch
                WHERE "desc" IS NOT NULL
                  AND views IS NOT NULL
            )
            SELECT
                row_id,
                views,
                "desc"
            FROM tokenized
            WHERE list_contains(
                words,
                '{escaped_word}'
            )
        """

        return con.execute(query).pl()

    finally:
        con.unregister("batch")


def compare_word_rows(
    polars_result: pl.DataFrame,
    cudf_result: pl.DataFrame,
    duckdb_result: pl.DataFrame,
    word: str,
) -> tuple[
    pl.DataFrame,
    pl.DataFrame,
    pl.DataFrame,
]:
    polars_ids = polars_result.select("row_id")
    cudf_ids = cudf_result.select("row_id")
    duckdb_ids = duckdb_result.select("row_id")

    polars_only = (
        polars_result
        .join(
            cudf_ids,
            on="row_id",
            how="anti",
        )
        .with_columns(
            pl.lit("polars_only").alias("difference"),
        )
    )

    cudf_only = (
        cudf_result
        .join(
            polars_ids,
            on="row_id",
            how="anti",
        )
        .with_columns(
            pl.lit("cudf_only").alias("difference"),
        )
    )

    duckdb_only = (
        duckdb_result
        .join(
            polars_ids,
            on="row_id",
            how="anti",
        )
        .with_columns(
            pl.lit("duckdb_only_vs_polars").alias("difference"),
        )
    )

    if not polars_only.is_empty():
        print()
        print(f"POLARS ONLY: {word}")
        print(polars_only.head(MAX_PRINTED_EXAMPLES))

    if not cudf_only.is_empty():
        print()
        print(f"cuDF ONLY: {word}")
        print(cudf_only.head(MAX_PRINTED_EXAMPLES))

    if not duckdb_only.is_empty():
        print()
        print(f"DUCKDB ONLY VS POLARS: {word}")
        print(duckdb_only.head(MAX_PRINTED_EXAMPLES))

    # Also explicitly check DuckDB vs cuDF.
    duckdb_only_vs_cudf = duckdb_result.join(
        cudf_ids,
        on="row_id",
        how="anti",
    )

    cudf_only_vs_duckdb = cudf_result.join(
        duckdb_ids,
        on="row_id",
        how="anti",
    )

    if not duckdb_only_vs_cudf.is_empty():
        print()
        print(f"DUCKDB ONLY VS cuDF: {word}")
        print(
            duckdb_only_vs_cudf.head(
                MAX_PRINTED_EXAMPLES,
            )
        )

    if not cudf_only_vs_duckdb.is_empty():
        print()
        print(f"cuDF ONLY VS DUCKDB: {word}")
        print(
            cudf_only_vs_duckdb.head(
                MAX_PRINTED_EXAMPLES,
            )
        )

    return (
        polars_only,
        cudf_only,
        duckdb_only,
    )


def run_word_analysis(
    word: str,
) -> None:
    print()
    print("=" * 80)
    print(f"WORD ANALYSIS: {word}")
    print("=" * 80)
    print(f"batch size: {BATCH_SIZE:,}")

    con = duckdb.connect()

    polars_total = 0
    cudf_total = 0
    duckdb_total = 0

    polars_rows = 0
    cudf_rows = 0
    duckdb_rows = 0

    polars_only_frames: list[pl.DataFrame] = []

    cudf_only_frames: list[pl.DataFrame] = []

    duckdb_only_frames: list[pl.DataFrame] = []

    try:
        for batch_index, table in enumerate(
            iter_batches_with_row_id(
                PARQUET_PATH,
                BATCH_SIZE,
            ),
            start=1,
        ):
            polars_result = find_word_rows_polars(
                table,
                word,
            )

            cudf_result = find_word_rows_cudf(
                table,
                word,
            )

            duckdb_result = find_word_rows_duckdb(
                con,
                table,
                word,
            )

            polars_batch_views = int(polars_result["views"].sum()) if len(polars_result) else 0

            cudf_batch_views = int(cudf_result["views"].sum()) if len(cudf_result) else 0

            duckdb_batch_views = int(duckdb_result["views"].sum()) if len(duckdb_result) else 0

            polars_total += polars_batch_views
            cudf_total += cudf_batch_views
            duckdb_total += duckdb_batch_views

            polars_rows += len(polars_result)
            cudf_rows += len(cudf_result)
            duckdb_rows += len(duckdb_result)

            (
                polars_only,
                cudf_only,
                duckdb_only,
            ) = compare_word_rows(
                polars_result,
                cudf_result,
                duckdb_result,
                word,
            )

            if not polars_only.is_empty():
                polars_only_frames.append(polars_only)

            if not cudf_only.is_empty():
                cudf_only_frames.append(cudf_only)

            if not duckdb_only.is_empty():
                duckdb_only_frames.append(duckdb_only)

            print(
                f"batch {batch_index}: "
                f"Polars={polars_batch_views:,} "
                f"cuDF={cudf_batch_views:,} "
                f"DuckDB={duckdb_batch_views:,} | "
                f"ΔcuDF="
                f"{cudf_batch_views - polars_batch_views:+,}"
            )

    finally:
        con.close()

    print()
    print("=" * 80)
    print("FINAL RESULT")
    print("=" * 80)

    print(f"word:              {word}")
    print()

    print(f"Polars views:      {polars_total:,}")
    print(f"cuDF views:        {cudf_total:,}")
    print(f"DuckDB views:      {duckdb_total:,}")

    print()

    print(f"cuDF - Polars:     {cudf_total - polars_total:+,}")
    print(f"DuckDB - Polars:   {duckdb_total - polars_total:+,}")

    print()

    print(f"Polars rows:       {polars_rows:,}")
    print(f"cuDF rows:         {cudf_rows:,}")
    print(f"DuckDB rows:       {duckdb_rows:,}")

    polars_only_count = sum(len(frame) for frame in polars_only_frames)

    cudf_only_count = sum(len(frame) for frame in cudf_only_frames)

    duckdb_only_count = sum(len(frame) for frame in duckdb_only_frames)

    print()

    print(f"Polars only rows:  {polars_only_count:,}")
    print(f"cuDF only rows:    {cudf_only_count:,}")
    print(f"DuckDB only rows:  {duckdb_only_count:,}")

    if polars_only_frames:
        polars_only = pl.concat(polars_only_frames)

        print()
        print("=" * 80)
        print("POLARS ONLY - VIEW CONTRIBUTION")
        print("=" * 80)

        print(
            polars_only.select(
                pl.len().alias("rows"),
                pl.col("views").sum().alias("views"),
            )
        )

    if cudf_only_frames:
        cudf_only = pl.concat(cudf_only_frames)

        print()
        print("=" * 80)
        print("cuDF ONLY - VIEW CONTRIBUTION")
        print("=" * 80)

        print(
            cudf_only.select(
                pl.len().alias("rows"),
                pl.col("views").sum().alias("views"),
            )
        )

    if duckdb_only_frames:
        duckdb_only = pl.concat(duckdb_only_frames)

        print()
        print("=" * 80)
        print("DUCKDB ONLY - VIEW CONTRIBUTION")
        print("=" * 80)

        print(
            duckdb_only.select(
                pl.len().alias("rows"),
                pl.col("views").sum().alias("views"),
            )
        )


def run_tokenizer_analysis(
    args: argparse.Namespace,
) -> None:
    output_path = get_output_path(
        args.output,
        args.vocab,
    )

    (
        language_words,
        language_words_cudf,
    ) = load_vocabulary(
        args.vocab,
        args.stopwords,
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

    if args.word is not None:
        run_word_analysis(args.word)
    else:
        run_tokenizer_analysis(args)


if __name__ == "__main__":
    main()
