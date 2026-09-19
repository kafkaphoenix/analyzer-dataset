import subprocess

BATCH_SIZES = [500_000, 1_000_000, 2_500_000, 5_000_000, 10_000_000, 15_000_000, 20_000_000]
ENGINES = ["cpu", "gpu"]


def run_benchmark(engine: str, batch_size: int) -> str:
    print(f"▶ Starting {engine.upper()} with batch_size={batch_size:,}...", end="", flush=True)

    batch_flag = "--cpu-batch-size" if engine == "cpu" else "--gpu-batch-size"

    # Base command structure pointing to the correct Typer entrypoint
    cmd = ["uv", "run", "process", "-q", engine, batch_flag, str(batch_size)]

    # OPTIMIZATION FIXED: Conditionally inject the monitor flag (-m) ONLY for the CPU
    # engine. Since capture_output=True is active below, Rich's terminal layout updates
    # will be fully silenced, preventing console clutter while forcing the chunked execution path.
    if engine == "cpu":
        cmd.append("-m")

    try:
        # capture_output=True absorbs both standard outputs, rendering the background execution invisible
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
    print(" ▶ Starting Benchmark Matrix ")
    print("=" * 60)

    results: dict[int, dict[str, str]] = {size: {} for size in BATCH_SIZES}
    for batch_size in BATCH_SIZES:
        for engine in ENGINES:
            results[batch_size][engine] = run_benchmark(engine, batch_size)

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
