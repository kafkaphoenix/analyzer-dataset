# Social Media Dataset Project

Framework offering different query engines for processing and analyzing massive social media datasets efficiently.

## Prerequisites

This project is built using **Python 3.13** and uses **`uv`** for environment management. Ensure you have [`uv`](https://docs.astral.sh/uv/getting-started/installation/) installed on your system.

## Directory Structure

```text
analyzer_dataset/

├── benchmarks/             # Automated benchmark suites
├── datasets/               # Input source storage (vocabulary and Parquet video data)
├── docs/                   # Architecture specifications and hardware reports
├── results/                # Query exports, performance metrics, and historical runs
├── src/
│   └── analyzer_dataset/     # Package root application namespace
│       ├── cli.py          # Command-line interface (Typer)
│       ├── config.py       # Application configuration and settings validation
│       ├── queries.py      # Query engine selection and construction
│       ├── domain/         # Shared domain definitions and tokenizer patterns
│       ├── repository/     # Data infrastructure and engine adapters
│       │   ├── engines/
│       │   │   ├── cpu.py           # Polars CPU implementation
│       │   │   ├── gpu.py           # Hybrid Polars GPU implementation
│       │   │   ├── cudf.py          # Native cuDF implementation
│       │   │   ├── duckdb.py        # DuckDB implementation
│       │   │   └── polars_common.py # Shared Polars cleaning implementation
│       │   └── vocabulary.py        # Vocabulary loading and filtering
│       └── usecase/         # Application workflows and query abstractions
├── Makefile                 # Formatting, type checking and verification commands
├── pyproject.toml           # Project metadata and dependency configuration
└── uv.lock                 # Lockfile ensuring reproducible dependency versions
```

The tokenizer definitions and regex patterns are centralized in `domain/tokenizer.py`.

The Polars CPU and hybrid GPU implementations share the same `clean_desc_polars()` implementation from `repository/engines/polars_common.py`. The native cuDF and DuckDB implementations provide their own engine-specific cleaning functions.

The tokenizer tests and differential diagnostics use these same production cleaning implementations to avoid maintaining separate copies of the tokenization logic.

---

## Configuration

Copy [`.env.example`](.env.example) to `.env` and adjust the values for your environment.

CLI options can override values loaded from `.env`. The final configuration is validated through Pydantic Settings.

---

## Usage Guide

### 1. Set Up Environment & Dependencies

Initialize the project virtual environment:

```bash
uv sync
```

### 2. Prepare Data

Place the social media dataset files inside the `datasets/` directory.

The dataset and vocabulary paths can be configured through the `.env` file.

### 3. Process Data

Run the baseline CPU implementation:

```bash
uv run process -q cpu
```

Run the hybrid Polars GPU implementation:

```bash
uv run process -q gpu
```

Run the GPU implementation with real-time system monitoring:

```bash
uv run process -q gpu -m
```

When monitoring is enabled, the monitoring infrastructure introduces additional execution overhead.

The GPU implementation always processes data in batches because the GPU has a more limited memory budget than system RAM. Batch size therefore affects GPU execution with or without monitoring.

Override the GPU batch size for performance testing:

```bash
uv run process -q gpu -gb 2500000
```

Run the native cuDF implementation:

```bash
uv run process -q cudf
```

Override the cuDF Parquet chunk read limit. For example, to use 1024 MiB:

```bash
uv run process -q cudf --cudf-chunk-read-limit 1024
```

The value is converted to bytes internally before being passed to the cuDF reader.

Run DuckDB using a specific number of threads:

```bash
uv run process -q duckdb --duckdb-threads 16
```

Threads cannot exceed the number of available CPU cores on the system.

CLI options take precedence over `.env` settings.

### Monitoring and Batch Execution

The CPU implementation has two execution paths:

* Without monitoring, it uses a single fused lazy Polars query and does not use the configured batch size.
* With monitoring enabled, it uses `collect_batches()` and the configured CPU batch size so progress can be reported during execution.

The GPU implementation always uses `collect_batches()` because intermediate tokenization and `explode()` operations can substantially increase the number of rows held in memory.

---

## Query Engines

Four query implementations are provided:

| Engine   | Description                                                                                                                       |
| -------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `cpu`    | Polars CPU implementation using streaming execution                                                                               |
| `gpu`    | Hybrid Polars implementation using CPU for tokenizer operations not supported by the GPU engine and GPU execution for aggregation |
| `cudf`   | Native cuDF implementation using `pylibcudf` and cuDF                                                                             |
| `duckdb` | DuckDB SQL implementation using its parallel execution engine                                                                     |

All implementations perform the same logical operation:

1. Read video descriptions and view counts.
2. Remove corrupted payloads and tokenize descriptions.
3. Remove URLs, emails, mentions and hashtags.
4. Normalize ASCII uppercase characters to lowercase.
5. Extract alphabetic English word candidates.
6. Filter tokens against the configured English vocabulary.
7. Aggregate total views per word.
8. Sort by total views and return the configured top-k results.

Each engine uses its own native implementation of these operations. Shared tokenizer definitions are kept in the domain layer, while engine-specific cleaning logic remains in the corresponding repository adapter.

---

## Benchmarking

The `benchmarks/` directory contains automation scripts used to evaluate engine-specific parameters such as batch size and cuDF Parquet chunk size.

The benchmark scripts execute the same production query entry points used by the CLI.

For example, the batch-size benchmark compares CPU and GPU execution across different batch sizes, while the cuDF benchmark measures the effect of different Parquet chunk read limits.

When comparing CPU and GPU batch sizes, note that the CPU benchmark enables monitoring so that the CPU implementation enters its chunked execution path. The unmonitored CPU path deliberately bypasses batching and therefore is not a batch-size benchmark.

System monitoring itself adds execution overhead, so monitored and unmonitored timings should not be treated as directly equivalent performance measurements.
