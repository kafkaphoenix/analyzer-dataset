# Performance Report: CPU, Hybrid GPU, Native cuDF and DuckDB

## 1. Overview

This report evaluates four implementations of the same TikTok dataset query:

* **CPU Polars**: pure CPU execution using Polars.
* **Hybrid Polars GPU**: using the `cuDF-Polars` GPU engine where supported, with unsupported operations remaining on the CPU.
* **Native cuDF**: direct GPU dataframe execution using cuDF and `pylibcudf`.
* **DuckDB**: vectorized SQL execution using DuckDB.

The workload processes approximately **166.4 million TikTok records** and calculates the total number of views associated with the most frequent English words appearing in video descriptions.

The common logical pipeline is:

**Parquet Input → Text Cleaning → Regex Tokenization → Explode → English Vocabulary Match → Group By → SUM(views) → Top-K**

> The primary benchmark uses **unmonitored execution**, allowing the engines to be compared without the additional overhead introduced by runtime resource monitoring.

---

## 2. Benchmark Environment

### Hardware

* **CPU:** Intel Core i5-12600K
* **GPU:** NVIDIA GeForce RTX 5080 — 16 GB VRAM
* **System RAM:** 32 GB
* **Dataset:** ~166,423,554 rows
* **Input format:** Parquet (ZSTD)

### Implementations

| Engine   | Execution Model         | GPU Usage | Description                               |
| -------- | ----------------------- | --------: | ----------------------------------------- |
| `cpu`    | Polars / CPU            |      None | Fully CPU-based vectorized processing     |
| `gpu`    | Polars + cuDF-Polars    |   Partial | Hybrid CPU/GPU execution                  |
| `cudf`   | Native cuDF + pylibcudf |      High | Direct GPU dataframe execution            |
| `duckdb` | DuckDB SQL              |      None | CPU-based vectorized relational execution |

---

## 3. Query Pipeline

All implementations perform the same logical operation:

1. Read the `desc` and `views` columns from the Parquet dataset.
2. Remove rows with missing descriptions or view counts.
3. Convert descriptions to lowercase.
4. Clean the text using regular expressions.
5. Extract words using a regular expression.
6. Remove duplicate words appearing within the same description.
7. Explode the word lists into individual rows.
8. Match the resulting words against the English vocabulary.
9. Group matching words.
10. Sum their associated views.
11. Select the top five words.

The vocabulary matching stage is effectively a **semi-join**: only words that exist in the English vocabulary are retained.

---

## 4. Execution Benchmark

The following measurements were collected:

### Query Times

| Engine                |        Query Time |
| --------------------- | ----------------: |
| **Native cuDF**       |       **16.97 s** |
| **CPU Polars**        |       **20.31 s** |
| **Hybrid Polars GPU** |       **21.22 s** |
| **DuckDB**            |       **33.57 s** |

Native cuDF is approximately **3.34 seconds faster than CPU Polars**, representing roughly a **16.5% reduction in query execution time**.

---

## 5. Batch Size Benchmark

Earlier testing of the CPU and Hybrid GPU implementations showed that CPU Polars is relatively stable across batch sizes, while the Hybrid GPU implementation is more sensitive to batch size.

| Batch Size |         CPU |  Hybrid GPU |
| ---------: | ----------: | ----------: |
|    500,000 |     19.44 s |     29.72 s |
|  1,000,000 |     19.08 s |     22.57 s |
|  2,500,000 |     19.87 s |     21.46 s |
|  5,000,000 |     19.54 s |     20.42 s |
| 10,000,000 | **19.13 s** | **19.95 s** |
| 15,000,000 |     19.70 s | **19.95 s** |
| 20,000,000 |     20.22 s |     20.40 s |

The Hybrid GPU implementation benefits considerably from larger batches. Small batches introduce additional CPU/GPU execution and transfer overhead, while batches around **10–15 million rows** provide the best observed results.

---

## 6. Technical Limitation of Polars GPU

The limitation observed in this project is **not that cuDF cannot process strings, regular expressions, lists, or joins**.

The limitation is specifically the current level of **operation support in the Polars GPU engine** for the operations required by this query.

The Polars implementation contains operations such as:

```python
.str.to_lowercase()
.str.replace_all(...)
.str.extract_all(...)
.list.unique()
.explode(...)
```

When these operations cannot be executed by the GPU engine, the execution path falls back to CPU processing.

Consequently, although the query is configured to use the GPU engine, it does not represent a fully GPU-executed query.

Native cuDF avoids this specific limitation because the query is expressed directly through the cuDF dataframe API rather than being translated from Polars operations.

---

## 7. Resource Usage

Runtime monitoring was also performed separately to evaluate CPU, GPU, RAM and VRAM utilization.

### Monitored Results

| Engine          |  Query Time |   CPU |       GPU |     RAM |
| --------------- | ----------: | ----: | --------: | ------: |
| **Native cuDF** | **16.62 s** |  **5.0%** | **85.0%** |  **6.7 GB** |
| **Hybrid GPU**  |     21.78 s | 100% |     33.0% |  10 GB |
| **CPU Polars**  |    25.58 s* | 100% |        0% | 16 GB |
| **DuckDB**      |     39.74 s | 100% |        0% |  16 GB |

> Because monitoring itself introduces some execution overhead, these measurements should **not** be used as the primary timing benchmark.