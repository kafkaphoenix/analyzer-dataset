from __future__ import annotations

import subprocess

# Configured in MiB integers to satisfy Pydantic Field constraints [ge=256, le=2048] directly via CLI
CHUNK_READ_LIMITS_MIB = [256, 512, 1024, 2048]


def run_benchmark(chunk_read_limit_mib: int) -> str:
    """
    ==================================================
    Chunk Read Limit     | cuDF Time
    --------------------------------------------------
    256 MiB              | 20.31s
    512 MiB              | 16.87s
    1024 MiB             | 15.82s
    2048 MiB             | 16.52s
    ==================================================
    """
    print(f"▶ Starting CUDF with chunk_read_limit={chunk_read_limit_mib} MiB...", end="", flush=True)

    # FIXED: Passes the raw MiB numerical scale integer to align with Pydantic validation barriers seamlessly
    cmd = ["uv", "run", "process", "-q", "cudf", "--cudf-chunk-read-limit", str(chunk_read_limit_mib)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        time_taken = "N/A"
        for line in result.stdout.splitlines():
            if "Query time:" in line:
                time_taken = line.replace("Query time:", "").strip()
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

    results = {}
    for limit_mib in CHUNK_READ_LIMITS_MIB:
        results[limit_mib] = run_benchmark(limit_mib)

    print("\n" + "=" * 50)
    print(f"{'Chunk Read Limit':<20} | {'cuDF Time':<15}")
    print("-" * 50)
    for limit_mib, time_taken in results.items():
        print(f"{f'{limit_mib} MiB':<20} | {time_taken:<15}")
    print("=" * 50)


if __name__ == "__main__":
    main()
