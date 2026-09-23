from __future__ import annotations

import polars as pl

from tiktok_dataset.domain.data_quality import CORRUPTED_PAYLOAD_PATTERN
from tiktok_dataset.domain.tokenizer import (
    ASCII_LOWER_MAP,
    CLEAN_PATTERN_POLARS,
)


def clean_desc_polars(desc: pl.Expr) -> pl.Expr:
    """
    Apply the shared native Polars description-cleaning pipeline.

    Order:

    1. Remove known corrupted binary payloads.
    2. ASCII lowercase A-Z.
    3. Remove URLs, emails, mentions and hashtags.
    """
    return (
        desc.str.replace(
            CORRUPTED_PAYLOAD_PATTERN,
            "",
        )
        .str.replace_many(
            ASCII_LOWER_MAP,
        )
        .str.replace_all(
            CLEAN_PATTERN_POLARS,
            " ",
        )
    )
