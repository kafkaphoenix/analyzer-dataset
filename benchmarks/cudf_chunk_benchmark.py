from __future__ import annotations

import subprocess

CHUNK_READ_LIMITS = [
    64 * 1024 * 1024,    # 64 MB
    128 * 1024 * 1024,   # 128 MB
    256 * 1024 * 1024,   # 256 MB
    512 * 1024 * 1024,   # 512 MB
    1024 * 1024 * 1024,  # 1 GB
    2048 * 1024 * 1024,  # 2 GB
    4096 * 1024 * 1024,  # 4 GB
]


def format_size(size: int) -> str:
    if size >= 1024**3:
        return f"{size / 1024**3:g} GB"

    return f"{size / 1024**2:g} MB"


def run_benchmark(chunk_read_limit: int) -> str:
    """
    ==================================================
    Chunk Read Limit     | cuDF Time      
    --------------------------------------------------
    64 MB                | 33.24s         
    128 MB               | 23.90s         
    256 MB               | 19.87s         
    512 MB               | 16.05s         
    1 GB                 | 16.54s         
    2 GB                 | 16.08s         
    4 GB                 | 15.99s         
    ==================================================
    """
    size = format_size(chunk_read_limit)

    print(
        f"▶ Starting CUDF with chunk_read_limit={size}...",
        end="",
        flush=True,
    )

    cmd = [
        "uv",
        "run",
        "process",
        "-q",
        "cudf",
        "--cudf-chunk-read-limit",
        str(chunk_read_limit),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )

        time_taken = "N/A"

        for line in result.stdout.splitlines():
            if "Query time:" in line:
                time_taken = line.replace(
                    "Query time:",
                    "",
                ).strip()
                break

        print(f" ✔ Completed in {time_taken}!")
        return time_taken

    except subprocess.CalledProcessError as e:
        print(" ❌ ERROR")
        print(f"Error details:\n{e.stderr}")
        return "ERROR"


def main() -> None:
    print("=" * 60)
    print(" ▶ Starting cuDF Chunk Read Limit Benchmark ")
    print("=" * 60)

    results: dict[int, str] = {}

    for chunk_read_limit in CHUNK_READ_LIMITS:
        results[chunk_read_limit] = run_benchmark(
            chunk_read_limit,
        )

    print("\n" + "=" * 50)
    print(
        f"{'Chunk Read Limit':<20} | {'cuDF Time':<15}"
    )
    print("-" * 50)

    for chunk_read_limit, time_taken in results.items():
        size = format_size(chunk_read_limit)

        print(
            f"{size:<20} | {time_taken:<15}"
        )

    print("=" * 50)


if __name__ == "__main__":
    main()