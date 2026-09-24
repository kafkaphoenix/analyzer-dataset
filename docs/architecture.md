# Technical Architecture Design

This document details the software design, layered data flows, execution pipeline strategies, configuration model, and engine comparison logic used in the Social Media Analyzer Dataset Project.

---

## 1. Multi-Engine Topology

The project is architected to compare **four distinct execution engines** solving the same logical textual query pipeline over a large social media Parquet dataset:

1. **`cpu`**: Native Polars execution on the host CPU using its vectorized Rust execution engine and streaming execution.

2. **`gpu`**: A hybrid Polars architecture using the cuDF-Polars GPU engine where supported. Operations that are not currently supported by the Polars GPU engine, particularly parts of the string, regex, list, and explode processing pipeline, remain CPU-bound.

3. **`duckdb`**: Vectorized relational processing using DuckDB's in-process analytical SQL engine. The workload is expressed as a relational pipeline including tokenization, vocabulary matching, aggregation, and Top-K selection.

4. **`cudf`**: Direct GPU dataframe execution using native **cuDF and pylibcudf**, avoiding the Polars GPU translation layer and providing direct access to GPU-accelerated dataframe and string operations.

All four engines implement the same logical workload while retaining engine-specific execution strategies.

---

## 2. Structural Layer Layout

The project follows a layered architecture separating application orchestration, query selection, infrastructure adapters, and domain definitions.

```text
┌─────────────────────────────────────────────────────────┐
│                       CLI LAYER                         │
│                 src/analyzer_dataset/cli.py               │
│       Parses commands and runtime query options         │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    USECASE LAYER                        │
│                 src/analyzer_dataset/usecase/              │
│     Query orchestration, timing and progress handling   │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                QUERY SELECTION LAYER                    │
│             src/analyzer_dataset/queries.py               │
│       Maps engine names to concrete implementations     │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                   REPOSITORY LAYER                      │
│              src/analyzer_dataset/repository/             │
│                                                         │
│   ┌─────────────────────────────────────────────────┐   │
│   │                    engines/                     │   │
│   │                                                 │   │
│   │ cpu.py              Polars CPU                  │   │
│   │ gpu.py              Hybrid Polars GPU           │   │
│   │ cudf.py             Native cuDF                 │   │
│   │ duckdb.py           DuckDB SQL                  │   │
│   │ polars_common.py    Shared Polars cleaning     │   │
│   └─────────────────────────────────────────────────┘   │
│                                                         │
│   vocabulary.py      Vocabulary loading/filtering       │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    DOMAIN LAYER                         │
│             src/analyzer_dataset/domain/                   │
│                                                         │
│   tokenizer.py       Shared tokenizer definitions,      │
│                      regex patterns and constants       │
│   data_quality.py    Corrupted payload handling         │
└─────────────────────────────────────────────────────────┘
```

The domain layer contains reusable tokenizer definitions and data-quality rules.

Engine-specific cleaning implementations are kept in the repository layer:

* `polars_common.py` provides the shared `clean_desc_polars()` implementation used by both Polars engines.
* `cudf.py` provides `clean_desc_cudf()`.
* `duckdb.py` provides `clean_desc_duckdb()`.

This structure allows the production query implementations and tokenizer diagnostics/tests to reuse the exact same engine-specific cleaning logic rather than maintaining separate copies.

---

## 3. Common Query Pipeline

All four engines implement the same logical workload so their execution strategies can be compared under equivalent processing rules.

```text
Parquet Dataset
      │
      ▼
Read desc + views
      │
      ▼
Remove known corrupted payloads
      │
      ▼
ASCII lowercase normalization
      │
      ▼
Remove URLs, emails, mentions and hashtags
      │
      ▼
Regex tokenization
      │
      ▼
Unique words per row
      │
      ▼
Semi join with English vocabulary
      │
      ▼
Aggregate SUM(views) by word
      │
      ▼
Top-K selection
      │
      ▼
Sort by total views
```

The logical transformation is shared across engines, while the underlying implementation is native to each execution framework.

---

## 4. Tokenization Architecture

Tokenizer definitions are centralized in:

```text
src/analyzer_dataset/domain/tokenizer.py
```

This module contains the shared pattern definitions and constants used by the engine implementations.

The tokenizer patterns and normalization rules are centralized in the
domain layer. Each engine then applies those rules using its native
string and regular-expression operations.

### Polars

Both CPU Polars and the hybrid GPU implementation use:

```text
repository/engines/polars_common.py
    └── clean_desc_polars()
```

This function performs the production Polars cleaning sequence and is reused by both query implementations and their tokenizer diagnostics.

### cuDF

The native cuDF implementation uses:

```text
repository/engines/cudf.py
    └── clean_desc_cudf()
```

This function implements the production libcudf/cuDF cleaning pipeline and is reused by the tokenizer diagnostics.

### DuckDB

The DuckDB implementation uses:

```text
repository/engines/duckdb.py
    └── clean_desc_duckdb()
```

This function generates the production DuckDB SQL expression used by both the normal query path and diagnostic tooling.

The tokenizer tests and cross-engine mismatch diagnostics therefore exercise the same production cleaning implementations as the actual query engines.

---

## 5. Execution Strategies

Although all engines implement the same logical query, their physical execution strategies differ significantly.

### 5.1 CPU Polars

The CPU implementation uses Polars' native lazy and streaming execution.

There are two execution paths.

**Unmonitored execution**

The normal path uses a single fused lazy query:

```text
scan_parquet
    ↓
filter
    ↓
clean and tokenize
    ↓
explode
    ↓
vocabulary semi-join
    ↓
global aggregation
    ↓
Top-K
```

This path does not use the configured batch size and allows Polars to optimize execution as a single streaming query.

**Monitored execution**

When progress monitoring is enabled, the implementation uses `collect_batches()`.

```text
Parquet scan
    ↓
streaming batches
    ↓
tokenization
    ↓
aggregation per batch
    ↓
merge partial results
    ↓
Top-K
```

A row index is attached at scan time so progress reflects the position within the original input rather than the number of output rows after token explosion and vocabulary filtering.

---

### 5.2 Hybrid Polars GPU

The hybrid GPU implementation uses Polars' GPU engine for operations that can be executed efficiently through cuDF-Polars.

The tokenizer is deliberately executed using the shared native Polars implementation:

```text
Parquet
   ↓
Polars CPU filtering
   ↓
Polars CPU cleaning and regex tokenization
   ↓
explode / vocabulary filtering
   ↓
GPU aggregation
   ↓
GPU final reduction and Top-K
```

The workload is therefore a **hybrid CPU/GPU pipeline rather than a fully GPU-resident query**.

The implementation always processes the dataset through batches. This prevents the exploded token representation from becoming unnecessarily large in GPU memory and bounds the amount of data transferred into each GPU aggregation stage.

Batch size can therefore affect execution time through both memory pressure and repeated processing overhead.

---

### 5.3 Native cuDF

The native cuDF implementation bypasses the Polars GPU execution layer.

Parquet data is read using `pylibcudf` and `ChunkedParquetReader`, after which the data is processed using native cuDF/libcudf operations.

```text
Chunked Parquet reader
        ↓
cuDF dataframe
        ↓
production cuDF cleaning
        ↓
regex tokenization
        ↓
explode / vocabulary join
        ↓
batch aggregation
        ↓
partial-result concatenation
        ↓
global aggregation
        ↓
Top-K
```

The Parquet chunk read limit controls the amount of input data loaded into each processing chunk. The implementation therefore bounds memory consumption while still performing the transformation and aggregation stages on the GPU.

---

### 5.4 DuckDB

DuckDB expresses the workload as a vectorized analytical SQL query.

The normal execution path is a fused query:

```text
read_parquet()
      ↓
filter
      ↓
clean and tokenize
      ↓
list_distinct
      ↓
unnest
      ↓
vocabulary semi-join
      ↓
GROUP BY
      ↓
ORDER BY
      ↓
LIMIT
```

This avoids materializing an intermediate tokenization table during normal execution.

The monitored path introduces an explicit materialization boundary:

```text
Phase 1
read_parquet
    ↓
clean and tokenize
    ↓
CREATE TEMP TABLE tokenized_data

Phase 2
token expansion
    ↓
vocabulary filtering
    ↓
aggregation
    ↓
Top-K
```

This separate phase allows DuckDB query progress to be polled during the long-running tokenization stage.

---

## 6. Memory and Batching Strategy

The engines deliberately use different memory-control strategies.

| Engine   | Memory strategy                                                                                                                    |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `cpu`    | Fused streaming query when unmonitored; explicit batches only for the monitored path                                               |
| `gpu`    | Always processes streaming batches before GPU aggregation                                                                          |
| `cudf`   | Uses `ChunkedParquetReader` with a configurable chunk read limit                                                                   |
| `duckdb` | Uses DuckDB's vectorized execution and internal memory management; monitored mode materializes tokenization into a temporary table |

The different strategies are intentional because system RAM and GPU VRAM impose different practical constraints.

In particular, the hybrid Polars GPU implementation keeps batching enabled even without progress monitoring because tokenization and `explode()` can substantially increase the intermediate row count.

---

## 7. Configuration

Runtime configuration is loaded from environment variables using Pydantic Settings.

The default `.env` configuration used for the current benchmark environment is:

```text
ANALYZER_DATASET=datasets/videos-00.parquet

ANALYZER_ENGLISH_WORDS=datasets/english_words.txt

ANALYZER_ENGLISH_STOPWORDS=datasets/nltk_english_stopwords.txt

ANALYZER_MIN_WORD_LENGTH=3

ANALYZER_RESULTS_DIR=results

ANALYZER_TOP_K=5

ANALYZER_DEFAULT_BATCH_SIZE_CPU=1000000

ANALYZER_DEFAULT_BATCH_SIZE_GPU=10000000

ANALYZER_CUDF_CHUNK_READ_LIMIT=1024

ANALYZER_DUCKDB_THREADS=16

ANALYZER_MONITOR=true
```

The corresponding Pydantic settings model validates these values and exposes the cuDF chunk read limit in bytes to the query implementation.

Important configuration constraints include:

* CPU and GPU batch sizes must be between 500,000 and 20,000,000 rows.
* cuDF chunk read limits must be between 256 and 2048 MiB.
* DuckDB thread counts must not exceed the number of available CPU threads.
* CLI parameters override values loaded from `.env`.

The default GPU batch size is currently **10 million rows**, while the default CPU batch size is **1 million rows**.

---

## 8. Architectural Comparison

| Engine   | Execution               | String Processing | GPU Usage | Main Characteristic                                            |
| -------- | ----------------------- | ----------------- | --------- | -------------------------------------------------------------- |
| `cpu`    | Native Polars           | CPU               | None      | Fused or streaming CPU execution                               |
| `gpu`    | Polars + cuDF-Polars    | Hybrid CPU/GPU    | Partial   | GPU acceleration combined with CPU tokenizer operations        |
| `cudf`   | Native cuDF + pylibcudf | GPU               | High      | Direct GPU dataframe execution with chunked Parquet processing |
| `duckdb` | DuckDB SQL              | CPU               | None      | Vectorized relational execution with a fused query path        |

The comparison therefore evaluates more than raw hardware utilization. Relevant dimensions include:

* execution architecture
* supported operations
* batching strategy
* memory pressure
* CPU/GPU coordination
* query fusion
* progress-monitoring overhead
* Parquet read strategy

---

## 9. Current Benchmark Snapshot

The following timings are from the current full-dataset execution using the configured workload and `top_k=5`.

| Engine   | Query time |
| -------- | ---------: |
| `cpu`    |    17.89 s |
| `gpu`    |    18.85 s |
| `cudf`   |    30.36 s |
| `duckdb` |    51.04 s |

The current Top-K result for the CPU, hybrid GPU, and DuckDB implementations is:

| Word   |    Total views |
| ------ | -------------: |
| `like` | 38,260,773,895 |
| `one`  | 33,539,828,808 |
| `love` | 31,954,636,512 |
| `new`  | 28,776,351,509 |
| `get`  | 28,741,882,933 |

The benchmark figures are execution snapshots rather than fixed performance guarantees. Runtime can vary with system load, memory state, GPU state, batch size, and monitoring configuration.

---

## 10. Validation and Differential Diagnostics

The project includes tokenizer tests and full-dataset differential diagnostics to verify that the engine-specific implementations follow the same logical tokenizer behavior.

The diagnostics compare:

```text
Polars tokens
      ↕
cuDF tokens
      ↕
DuckDB tokens
```

Rows with different token sets can be recorded together with their source description, row ID, view count, and pairwise mismatch flags.

The diagnostic path uses the same production cleaning functions as the real query implementations:

```text
Polars  → clean_desc_polars()
cuDF    → clean_desc_cudf()
DuckDB  → clean_desc_duckdb()
```

This prevents diagnostic code from silently diverging from the production query logic.

---

## 11. Benchmarking

The `benchmarks/` directory contains automation scripts for evaluating engine-specific parameters.

Current benchmark dimensions include:

* CPU and GPU batch sizes
* cuDF Parquet chunk read limits
* query execution time
* monitored versus unmonitored execution

The CPU batch-size benchmark explicitly enables monitoring so that the CPU implementation uses its chunked execution path. Without monitoring, the CPU implementation intentionally uses the fused path and the configured CPU batch size is not part of the execution strategy.

The GPU implementation remains batched in both monitored and unmonitored execution.

Monitoring adds additional runtime overhead and should therefore be considered separately from pure unmonitored performance measurements.
