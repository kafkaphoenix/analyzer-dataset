# TikTok Dataset Project

Framework offering different query engines for processing and analyzing massive TikTok datasets efficiently.

## Prerequisites

This project is built using **Python 3.13** and utilizes **`uv`** for environment management. Ensure you have `uv` [installed](https://docs.astral.sh/uv/getting-started/installation/) on your system.

## Directory Structure

```text
tiktok-dataset/

├── benchmarks/          # Automation benchmark suites
├── datasets/            # Input source storage (vocabulary list and Parquet video data)
├── docs/                # Architecture specifications and technical hardware reports
├── results/             # Query exports, performance metrics, and historical runs
├── src/
│   └── tiktok_dataset/  # Package root application namespace
│       ├── cli.py       # Command-line interface (Typer)
│       ├── config.py    # Application configuration and settings validation
│       ├── queries.py   # Query engine selection and construction
│       ├── domain/      # Core data transformations (e.g., tokenization)
│       ├── repository/  # Data infrastructure and engine adapters
│       │   └── engines/ # cuDF, DuckDB, Polars CPU and Polars GPU implementations
│       └── usecase/     # Application workflows
├── Makefile             # Formatting, type checking and verification commands
├── pyproject.toml       # Project metadata and dependency configuration
└── uv.lock              # Lockfile ensuring reproducible dependency versions
```

---

## Configuration

Copy [.env.example](.env.example) to .env and adjust the values for your environment.

>CLI options can override values loaded from .env, with the final configuration validated through Pydantic Settings.

---

## Usage Guide

### 1. Set Up Environment & Dependencies

Initialize the project virtual environment:

```bash
uv sync
```

### 2. Prepare Data

Place the TikTok dataset files inside the `datasets/` directory.

> The dataset and vocabulary paths can be configured through the `.env` file.

### 3. Process Data

Run a baseline query using the CPU engine:

```bash
uv run process -q cpu
```

Run the GPU-accelerated Polars engine:

```bash
uv run process -q gpu
```

Run the GPU engine with real-time system monitoring:

```bash
uv run process -q gpu -m
```

> When system monitoring is enabled, the monitoring infrastructure introduces additional execution overhead.

Override the GPU batch size for performance testing:

```bash
uv run process -q gpu -gb 2500000
```

Run the native cuDF implementation with a custom Parquet chunk size of 1024 MiB:

```bash
uv run process -q cudf --cudf-chunk-read-limit 1024
```

> The value is converted to bytes internally before being passed to the cuDF reader.

Run DuckDB using a specific number of threads:

```bash
uv run process -q duckdb --duckdb-threads 16
```

> Threads cannot exceed the number of available CPU cores on the system.

> Note that CLI options take precedence over `.env` settings.

---

## Query Engines

Four query implementations are provided:

| Engine   | Description                                                   |
| -------- | ------------------------------------------------------------- |
| `cpu`    | Pure CPU implementation using Polars                          |
| `gpu`    | Polars GPU engine using cuDF-Polars and CPU for non-supported operations   |
| `cudf`   | Native cuDF implementation using `pylibcudf`                  |
| `duckdb` | DuckDB SQL implementation using its parallel execution engine |

All implementations perform the same logical operation: extract words from video descriptions, filter them against the English vocabulary, aggregate total views per word, sort by total views, and return the configured top-k results.

---

## Benchmarking

The `benchmarks/` directory contains automation scripts used to evaluate engine-specific parameters such as batch size and chunk size.
