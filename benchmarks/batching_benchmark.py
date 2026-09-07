import subprocess

BATCH_SIZES = [
    500_000,
    1_000_000,
    2_500_000,
    5_000_000,
    10_000_000,
    15_000_000,
    20_000_000,
]

ENGINES = ["cpu", "gpu"]


def run_benchmark(engine: str, batch_size: int) -> str:
    """
    ==================================================
    Batch Size      | CPU Time        | GPU Time       
    --------------------------------------------------
    500,000         | 19.44s          | 29.72s         
    1,000,000       | 19.08s          | 22.57s         
    2,500,000       | 19.87s          | 21.46s         
    5,000,000       | 19.54s          | 20.42s         
    10,000,000      | 19.13s          | 19.95s         
    15,000,000      | 19.70s          | 19.95s         
    20,000,000      | 20.22s          | 20.40s         
    ==================================================
    """
    print(f"▶ Starting {engine.upper()} with batch_size={batch_size:,}...", end="", flush=True)

    batch_flag = "--cpu-batch-size" if engine == "cpu" else "--gpu-batch-size"

    cmd = ["uv", "run", "process", "-q", engine, batch_flag, str(batch_size)]

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
    print(" ▶ Starting Benchmark Matrix (Without Monitor) ")
    print("=" * 60)

    results: dict[int, dict[str, str]] = {size: {} for size in BATCH_SIZES}

    for batch_size in BATCH_SIZES:
        for engine in ENGINES:
            time_taken = run_benchmark(engine, batch_size)
            results[batch_size][engine] = time_taken

    # Print a scannable summary in table format
    print("\n" + "=" * 50)
    print(f"{'Batch Size':<15} | {'CPU Time':<15} | {'GPU Time':<15}")
    print("-" * 50)
    for size, engines in results.items():
        size_str = f"{size:,}"
        cpu_t = engines.get("cpu", "N/A")
        gpu_t = engines.get("gpu", "N/A")
        print(f"{size_str:<15} | {cpu_t:<15} | {gpu_t:<15}")
    print("=" * 50)


if __name__ == "__main__":
    main()
