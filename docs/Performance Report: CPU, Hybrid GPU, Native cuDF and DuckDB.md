# Performance Report: CPU, Hybrid GPU, Native cuDF and DuckDB

## 1. Overview

This report evaluates four implementations of the same social media dataset query:

* **CPU Polars**: native CPU execution using Polars.
* **Hybrid Polars GPU**: Polars using the cuDF-Polars GPU engine where supported, with tokenizer operations remaining on the CPU.
* **Native cuDF**: direct GPU dataframe execution using cuDF and `pylibcudf`.
* **DuckDB**: vectorized analytical SQL execution using DuckDB.

The workload processes **166,423,554 social media records** and calculates the total number of views associated with the top English words appearing in video descriptions.

The common logical pipeline is:

**Parquet Input → Data Quality Cleanup → ASCII Lowercasing → Text Cleaning → Regex Tokenization → Per-Row Deduplication → English Vocabulary Semi-Join → Group By Word → SUM(views) → Top-K**

The primary benchmark uses the normal query execution path without explicit runtime monitoring. Monitoring introduces additional execution overhead and is evaluated separately.

---

## 2. Benchmark Environment

### Hardware

| Component        | Configuration                            |
| ---------------- | ---------------------------------------- |
| **CPU**          | Intel Core i5-12600K                     |
| **GPU**          | NVIDIA GeForce RTX 5080, 16 GB VRAM      |
| **System RAM**   | 32 GB                                    |
| **Dataset**      | 166,423,554 rows                         |
| **Input format** | ZSTD-compressed Parquet                  |
| **Python**       | 3.13                                     |
| **Polars**       | Native CPU and cuDF-Polars GPU execution |

### Default Configuration

The current benchmark configuration uses:

```text
ANALYZER_MIN_WORD_LENGTH=3
ANALYZER_TOP_K=5
ANALYZER_DEFAULT_BATCH_SIZE_CPU=1000000
ANALYZER_DEFAULT_BATCH_SIZE_GPU=10000000
ANALYZER_CUDF_CHUNK_READ_LIMIT=1024
ANALYZER_DUCKDB_THREADS=16
```

### Implementations

| Engine   | Execution Model         | GPU Usage | Description                     |
| -------- | ----------------------- | --------- | ------------------------------- |
| `cpu`    | Polars / CPU            | None      | Native vectorized CPU execution |
| `gpu`    | Polars + cuDF-Polars    | Partial   | Hybrid CPU/GPU execution        |
| `cudf`   | Native cuDF + pylibcudf | High      | Direct GPU dataframe execution  |
| `duckdb` | DuckDB SQL              | None      | Vectorized relational execution |

---

## 3. Query Pipeline

All implementations perform the same logical operation:

1. Read the `desc` and `views` columns from the Parquet dataset.
2. Remove rows with missing descriptions or view counts.
3. Remove known corrupted binary payloads.
4. Normalize ASCII uppercase characters to lowercase.
5. Remove URLs, emails, mentions and hashtags.
6. Extract words using the engine-specific native regular-expression implementation.
7. Remove duplicate words appearing within the same description.
8. Explode the word lists where required by the execution engine.
9. Match words against the configured English vocabulary.
10. Aggregate views by word.
11. Select the configured Top-K results.
12. Sort by total views.

The vocabulary matching stage is implemented as a **semi-join**, retaining only tokens present in the English vocabulary.

The tokenizer patterns are defined centrally, while the cleaning implementation is native to each execution engine. The Polars CPU and hybrid GPU implementations share the same production cleaning function.

---

## 4. Execution Strategies

### CPU Polars

The CPU implementation uses native Polars lazy and streaming execution.

The unmonitored path uses a fused query that allows Polars to optimize the full pipeline without explicit application-level batching.

The monitored path uses `collect_batches()` and performs intermediate aggregation per batch so that progress can be reported during execution.

This means the configured CPU batch size is relevant primarily to the monitored execution path.

### Hybrid Polars GPU

The hybrid GPU implementation uses the Polars GPU engine for supported operations, but the tokenizer remains based on the shared native Polars implementation.

The effective execution flow is:

```text
Parquet
    ↓
Polars CPU scan/filtering
    ↓
Polars CPU cleaning and regex tokenization
    ↓
List/explode/vocabulary processing
    ↓
GPU aggregation
    ↓
GPU final aggregation and Top-K
```

This is therefore a **hybrid CPU/GPU pipeline rather than a fully GPU-resident query**.

The implementation always processes the input through batches because tokenization and `explode()` can significantly expand the intermediate representation. Larger batches reduce repeated processing and CPU/GPU coordination overhead, while excessively large batches increase memory pressure.

### Native cuDF

The native cuDF implementation bypasses the Polars GPU translation layer.

Parquet data is read using `pylibcudf` and processed through native cuDF/libcudf operations:

```text
Chunked Parquet reader
    ↓
cuDF dataframe
    ↓
Native cuDF cleaning
    ↓
Regex tokenization
    ↓
List/explode/vocabulary processing
    ↓
Per-chunk aggregation
    ↓
Global aggregation
    ↓
Top-K
```

The Parquet chunk read limit controls how much source data is loaded per processing chunk.

### DuckDB

DuckDB executes the workload as a vectorized SQL pipeline.

The normal path can keep scanning, cleaning, tokenization, vocabulary matching, aggregation and Top-K selection inside a single fused query.

The monitored path materializes the tokenization stage into a temporary table so that progress can be polled before the global aggregation phase.

---

## 5. Current Execution Benchmark

The following measurements are from the latest full-dataset executions using:

```bash
uv run process -q cudf
uv run process -q cpu
uv run process -q gpu
uv run process -q duckdb
```

### Query Times

| Engine                |  Query Time |
| --------------------- | ----------: |
| **CPU Polars**        | **17.89 s** |
| **Hybrid Polars GPU** | **18.85 s** |
| **Native cuDF**       | **20.89 s** |
| **DuckDB**            | **51.04 s** |

Relative to the CPU result from this benchmark run:

* Hybrid Polars GPU: **0.96 s slower**, approximately **5.4%**.
* Native cuDF: **3.00 s slower**, approximately **16.8%**.
* DuckDB: **33.15 s slower**, approximately **185.3%**.

These figures represent a single current benchmark snapshot. Execution time can vary with system load, GPU state, memory state, Parquet caching, batch/chunk sizes and other runtime conditions.

---

## 6. Batch Size Benchmark

Earlier parameter sweeps evaluated the effect of batch size on the CPU and hybrid GPU implementations.

| Batch Size |         CPU |  Hybrid GPU |
| ---------: | ----------: | ----------: |
|    500,000 |     19.44 s |     29.72 s |
|  1,000,000 |     19.08 s |     22.57 s |
|  2,500,000 |     19.87 s |     21.46 s |
|  5,000,000 |     19.54 s |     20.42 s |
| 10,000,000 | **19.13 s** | **19.95 s** |
| 15,000,000 |     19.70 s | **19.95 s** |
| 20,000,000 |     20.22 s |     20.40 s |

These measurements show that the hybrid GPU implementation is more sensitive to batch size than the CPU implementation.

Small GPU batches introduce more repeated processing and CPU/GPU coordination overhead. The larger observed batches substantially reduce this overhead, with the strongest results in the approximately 10–15 million row range in this earlier sweep.

The current default GPU batch size is therefore **10,000,000 rows**.

The benchmark script enables monitoring for the CPU side specifically so that the CPU implementation enters its explicit chunked execution path. Without monitoring, the normal CPU execution path does not use the configured batch size in the same way.

---

## 7. cuDF Chunk Read Limit

Native cuDF was also evaluated using different Parquet chunk read limits.

Earlier measurements were:

| Chunk Read Limit |   cuDF Time |
| ---------------: | ----------: |
|          256 MiB |     20.31 s |
|          512 MiB |     16.87 s |
|         1024 MiB | **15.82 s** |
|         2048 MiB |     16.52 s |

The current configuration uses:

```text
ANALYZER_CUDF_CHUNK_READ_LIMIT=1024
```

which corresponds to a **1024 MiB** Parquet chunk read limit.

The measurements indicate that increasing the chunk size initially reduces repeated reader overhead, while very large chunks do not necessarily continue to improve execution time. The 1024 MiB configuration was therefore retained as the current default.

---

## 8. Technical Limitation of Polars GPU

The relevant limitation is not that GPU dataframe systems cannot process strings, regular expressions, lists or joins.

The limitation is the current level of **operation support in the Polars GPU engine** for the particular combination of operations required by this workload.

The query relies on tokenizer operations such as:

```python
.str.replace_all(...)
.str.extract_all(...)
.list.unique()
.explode(...)
```

The tokenizer is therefore deliberately executed through the native Polars implementation on the CPU, while supported aggregation stages are executed through the GPU engine.

As a result, the hybrid implementation is not a fully GPU-resident execution plan.

Native cuDF expresses the required operations directly through the cuDF/libcudf APIs, avoiding the Polars GPU translation layer.

---

## 9. Resource Usage

Runtime monitoring was evaluated separately from the primary unmonitored benchmark.

A previous monitored benchmark snapshot produced the following measurements:

| Engine          |  Query Time |      CPU |       GPU |        RAM |
| --------------- | ----------: | -------: | --------: | ---------: |
| **Native cuDF** | **16.62 s** | **5.0%** | **85.0%** | **6.7 GB** |
| **Hybrid GPU**  |     21.78 s |     100% |     33.0% |      10 GB |
| **CPU Polars**  |     25.58 s |     100% |        0% |      16 GB |
| **DuckDB**      |     39.74 s |     100% |        0% |      16 GB |

Monitoring itself introduces additional work, including progress collection and resource telemetry. These measurements should therefore be treated as a separate resource-utilization benchmark rather than as the primary query-time comparison.

The monitored and unmonitored timings are not directly interchangeable.

---

## 10. Resource and Execution Characteristics

The four implementations exhibit different execution characteristics:

| Engine   | Main Resource | Memory Strategy                             | Execution Characteristic                             |
| -------- | ------------- | ------------------------------------------- | ---------------------------------------------------- |
| `cpu`    | CPU           | Polars streaming                            | Fused unmonitored path or explicit monitored batches |
| `gpu`    | CPU + GPU     | Always batched                              | Hybrid tokenizer and GPU aggregation                 |
| `cudf`   | GPU           | Configurable Parquet chunks                 | Native GPU dataframe processing                      |
| `duckdb` | CPU           | DuckDB internal execution/memory management | Fused relational pipeline                            |

The comparison therefore evaluates more than raw compute throughput. Relevant factors include execution fusion, batching, memory pressure, GPU utilization, supported operations, Parquet read strategy and CPU/GPU coordination overhead.

---

## 11. Validation

The project includes automated tokenizer tests and full-dataset differential diagnostics.

The tokenizer diagnostics use the same production cleaning implementations as the query engines:

```text
Polars
    → clean_desc_polars()

cuDF
    → clean_desc_cudf()

DuckDB
    → clean_desc_duckdb()
```

This prevents the diagnostic implementation from becoming a second, independently maintained version of the production tokenizer.

The automated test suite currently passes:

```text
351 passed in 5.76s
```

The differential validation is used to investigate tokenizer behavior independently from the aggregate performance measurements.

---

## 12. Summary

The current benchmark demonstrates that the four engines solve the same logical workload using substantially different execution architectures.

The latest unmonitored full-dataset snapshot recorded:

```text
CPU Polars       17.89 s
Hybrid GPU       18.85 s
Native cuDF      20.89 s
DuckDB           51.04 s
```

The hybrid Polars implementation benefits from larger batches because CPU/GPU coordination is amortized over more input rows. Native cuDF uses a configurable Parquet chunking strategy to control GPU memory usage. DuckDB relies primarily on its vectorized relational execution model, while the CPU Polars implementation can use a fully fused streaming query when monitoring is disabled.

Performance should therefore be interpreted together with execution architecture, batch size, memory behavior and monitoring overhead rather than as a fixed property of the underlying hardware alone.
