from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert a Parquet file to CSV.")

    parser.add_argument(
        "input",
        type=Path,
        help="Input Parquet file.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input file does not exist: {args.input}")

    output = args.input.with_suffix(".csv")

    df = pl.read_parquet(args.input)
    df.write_csv(output)

    print(f"converted {args.input} -> {output}")


if __name__ == "__main__":
    main()
