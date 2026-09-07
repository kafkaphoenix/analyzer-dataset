# Technical Architecture Design

This document details the software design, layered data flows, execution pipeline strategies, and engine comparison logic used in the TikTok Dataset Project.

---

## 1. Multi-Engine Topology

The project is architected to compare **four distinct execution engines** solving the same textual query pipeline on a large Parquet dataset:

1. **`cpu`**: Native Polars execution on the host CPU using its vectorized Rust execution engine and batched/streaming processing.

2. **`polars_gpu`**: A hybrid Polars GPU architecture using the **cuDF-Polars GPU engine** where supported. Operations that are not currently supported by the Polars GPU engine, particularly parts of the string and regex processing pipeline, remain CPU-bound.

3. **`duckdb`**: Vectorized relational database processing using DuckDB's in-process analytical SQL engine. The complete query can be expressed as a relational pipeline, including tokenization, vocabulary matching, aggregation, and top-k selection.

4. **`cudf`**: Direct GPU dataframe execution using native **cuDF and pylibcudf**, avoiding the Polars GPU translation layer and providing direct access to GPU-accelerated dataframe and string operations.

---

## 2. Structural Layer Layout

The project follows a clean architectural model separating orchestration, functional execution, infrastructure drivers, and domain policies:

```text
 ┌─────────────────────────────────────────────────────────┐
 │                       CLI LAYER                         │
 │                  src/tiktok_dataset/cli.py              │
 │  Parses command-line options and builds the query plan  │
 └───────────┬────────────────────────────────┬────────────┘
             │                                │
             ▼                                ▼
 ┌───────────────────────┐        ┌───────────────────────┐
 │    USECASE LAYER      │        │    USECASE LAYER      │
 │      benchmark.py     │◄───────┤       monitor.py      │
 │  Orchestrates query   │        │  Collects live system │
 │  execution and timing │        │  resource telemetry   │
 └───────────┬───────────┘        └───────────────────────┘
             │
             ▼
 ┌─────────────────────────────────────────────────────────┐
 │                  QUERY SELECTION LAYER                  │
 │             src/tiktok_dataset/queries.py               │
 │  Maps engine names to their concrete query implementations│
 └───────────┬─────────────────────────────────────────────┘
             │
             ▼
 ┌─────────────────────────────────────────────────────────┐
 │                   REPOSITORY LAYER                      │
 │            src/tiktok_dataset/repository/               │
 │  Handles dataset access, vocabulary loading, and engine │
 │  implementations.                                       │
 │                                                         │
 │   engines/ → [polars_cpu, polars_gpu, duckdb, cudf]     │
 └───────────┬─────────────────────────────────────────────┘
             │
             ▼
 ┌─────────────────────────────────────────────────────────┐
 │                     DOMAIN LAYER                        │
 │              src/tiktok_dataset/domain/                 │
 │  Defines reusable data-processing rules, including      │
 │  tokenizer patterns and domain-level transformations.   │
 └─────────────────────────────────────────────────────────┘
```

---

## 3. Common Query Pipeline

All four engines implement the same logical workload so that their execution strategies can be compared under equivalent conditions.

```text
Parquet Dataset
      │
      ▼
Read `desc` + `views`
      │
      ▼
Text Cleaning
      │
      ▼
Regex Tokenization
      │
      ▼
Explode Words
      │
      ▼
Unique Words per Row
      │
      ▼
Semi Join with English Vocabulary
      │
      ▼
Group By Word
      │
      ▼
SUM(views)
      │
      ▼
Top-K Words
      │
      ▼
Sort by Total Views
```

---

## 4. Execution Strategies

Although all engines implement the same logical query, their execution strategies differ.

### CPU Polars

The CPU implementation performs the complete transformation pipeline on the host processor. The Parquet dataset is processed in batches to control memory usage while Polars performs vectorized transformations and aggregation.

### Polars GPU

The Polars GPU implementation uses the cuDF-Polars GPU engine for operations that can be executed on the GPU. However, the query relies heavily on string, regex, list, and explode operations.

The specific operations required by this workload are not all currently supported by the Polars GPU engine. Consequently, parts of the pipeline remain CPU-bound and data must move between CPU and GPU execution.

This makes the implementation a **hybrid CPU/GPU pipeline rather than a fully GPU-resident query**.

Batch size therefore has a significant effect on performance because smaller batches increase repeated CPU/GPU coordination and processing overhead.

### Native cuDF

The native cuDF implementation bypasses the Polars GPU translation layer.

Parquet data is read using `pylibcudf`, converted into cuDF dataframes, and processed directly using GPU dataframe operations. This allows the implementation to use native cuDF functionality for string processing, tokenization, list manipulation, joins, and aggregation.

The resulting partial aggregations from each input chunk are finally combined and the global top-k result is produced.

### DuckDB

DuckDB executes the workload as a relational SQL query. Its execution engine can combine scanning, filtering, tokenization, unnesting, vocabulary matching, aggregation, and top-k processing into a vectorized analytical pipeline.

A monitored execution mode can additionally materialize intermediate results to provide more detailed progress information during the long-running processing stage.

---

## 5. Architectural Comparison

| Engine       | Execution               | String Processing | GPU Usage | Main Characteristic                                      |
| ------------ | ----------------------- | ----------------- | --------- | -------------------------------------------------------- |
| `cpu`        | Polars / CPU            | CPU               | None      | Fully CPU-based vectorized execution                     |
| `polars_gpu` | Polars + cuDF-Polars    | Hybrid CPU/GPU    | Partial   | GPU acceleration limited by Polars GPU operation support |
| `cudf`       | Native cuDF + pylibcudf | GPU               | High      | Direct GPU dataframe execution                           |
| `duckdb`     | DuckDB SQL              | CPU               | None      | Fused/vectorized relational execution                    |

The comparison therefore evaluates not only raw hardware performance, but also the effect of **execution architecture, batching, supported operations, memory usage, and CPU/GPU coordination overhead**.
