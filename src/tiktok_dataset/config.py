from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings and validation schema utilizing Pydantic.
    Loads configuration matrices directly from environment variables
    prefixed with 'TIKTOK_' or an active local '.env' file layer.
    """

    dataset: Path = Path("datasets/videos-00.parquet")
    english_words: Path = Path("datasets/english_words.txt")

    results_dir: Path = Path("results")

    top_k: int = Field(
        default=5,
        gt=0,
    )

    # only relevant when using monitoring features
    default_batch_size_cpu: int = Field(
        default=1_000_000,
        ge=500_000,
        le=20_000_000,
    )

    default_batch_size_gpu: int = Field(
        default=10_000_000,
        ge=500_000,
        le=20_000_000,
    )

    cudf_chunk_read_limit_mib: int = Field(
        default=1024,
        ge=256,
        le=2048,
    )

    duckdb_threads: int | None = Field(
        default=None,
        gt=0,
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TIKTOK_",
        extra="ignore",
    )

    @field_validator("duckdb_threads")
    @classmethod
    def validate_duckdb_threads(cls, v: int | None) -> int | None:
        """Ensure the allocated DuckDB thread budget does not exceed physical CPU cores."""
        if v is None:
            return v

        max_threads = os.cpu_count() or 1

        if v > max_threads:
            raise ValueError(f"duckdb_threads must be less than or equal to the number of available threads ({max_threads})")

        return v

    @property
    def cudf_chunk_read_limit(self) -> int:
        """Convert the Mebibytes (MiB) limit specification dynamically into absolute bytes."""
        return self.cudf_chunk_read_limit_mib * 1024 * 1024
