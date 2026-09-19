from __future__ import annotations

import shutil
import subprocess
import threading
from dataclasses import dataclass
from types import TracebackType

import psutil

try:
    import pynvml
except ImportError:
    pynvml = None

BYTES_TO_GB = 1 / (1024**3)

_NATIVE_TEMP_SENSORS = ("coretemp", "cpu_thermal", "k10temp")
_TEMP_SAMPLE_INTERVAL = 5.0
_POWERSHELL_TIMEOUT = 2


@dataclass(frozen=True)
class SystemMetrics:
    cpu_percent: float
    process_threads: int
    cpu_temperature: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float

    gpu_available: bool = False
    gpu_utilization: float = 0.0
    gpu_memory_percent: float = 0.0
    gpu_memory_used_gb: float = 0.0
    gpu_memory_total_gb: float = 0.0
    gpu_temperature: float = 0.0


class SystemMonitor:
    """
    OS-level hardware utilization sampler.

    Tracks CPU, RAM, OS threads, and NVIDIA GPU metrics using low-level
    system calls. Spawns a background thread to safely capture CPU temperatures.
    """

    def __init__(self) -> None:
        self.process = psutil.Process()

        self._nvml_initialized = False
        self._gpu_handle = None
        self._initialize_gpu()

        self.process.cpu_percent(interval=None)

        self._cpu_temp = 0.0
        self._running = True
        self._stop_event = threading.Event()

        self._powershell_path = shutil.which("powershell.exe")

        self._temp_thread = threading.Thread(
            target=self._update_temp_loop,
            daemon=True,
            name="monitor-cpu-temp",
        )
        self._temp_thread.start()

    def __enter__(self) -> SystemMonitor:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def _initialize_gpu(self) -> None:
        """Initialize the NVML resource handle context safely."""
        if pynvml is None:
            return

        try:
            pynvml.nvmlInit()

            if pynvml.nvmlDeviceGetCount() == 0:
                return

            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._nvml_initialized = True
        except Exception:
            self._nvml_initialized = False
            self._gpu_handle = None

    def _update_temp_loop(self) -> None:
        """Background thread loop for sampling CPU temperature."""
        while self._running:
            temperature = self._get_native_cpu_temp()

            if temperature == 0.0 and self._running:
                temperature = self._get_powershell_cpu_temp()

            if temperature > 0.0:
                self._cpu_temp = temperature

            if self._stop_event.wait(timeout=_TEMP_SAMPLE_INTERVAL):
                break

    def _get_native_cpu_temp(self) -> float:
        """Read CPU temperature from native OS sensors."""
        try:
            temperatures = psutil.sensors_temperatures()

            for sensor in _NATIVE_TEMP_SENSORS:
                entries = temperatures.get(sensor)

                if entries:
                    return float(entries[0].current)

        except (OSError, ValueError, IndexError):
            pass

        return 0.0

    def _get_powershell_cpu_temp(self) -> float:
        """Read CPU temperature using the Windows thermal zone counter."""
        if not self._powershell_path:
            return 0.0

        command = [
            self._powershell_path,
            "-NoProfile",
            "-Command",
            ("(Get-Counter '\\Thermal Zone Information(*)\\Temperature').CounterSamples.CookedValue"),
        ]

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=_POWERSHELL_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return 0.0

        if result.returncode != 0:
            return 0.0

        return self._parse_powershell_temperature(result.stdout)

    def _parse_powershell_temperature(self, output: str) -> float:
        """Convert PowerShell thermal counter output into Celsius."""
        values = []

        for value in output.split():
            try:
                values.append(float(value))
            except ValueError:
                continue

        if not values:
            return 0.0

        raw_temperature = max(values)

        if raw_temperature > 1000:
            temperature = (raw_temperature / 10.0) - 273.15
        else:
            temperature = raw_temperature - 273.15

        if 0 < temperature < 110:
            return round(temperature, 1)

        return 0.0

    def sample(self) -> SystemMetrics:
        """Extract a point-in-time hardware snapshot vector."""
        try:
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=None)
            thread_count = self.process.num_threads()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            cpu_percent = 0.0
            thread_count = 1
            memory = psutil.virtual_memory()

        metrics = SystemMetrics(
            cpu_percent=min(cpu_percent, 100.0),
            process_threads=thread_count,
            cpu_temperature=self._cpu_temp,
            memory_percent=memory.percent,
            memory_used_gb=memory.used * BYTES_TO_GB,
            memory_total_gb=memory.total * BYTES_TO_GB,
        )

        if not self._nvml_initialized or pynvml is None:
            return metrics

        return self._sample_gpu_metrics(metrics)

    def _sample_gpu_metrics(self, metrics: SystemMetrics) -> SystemMetrics:
        """Add NVIDIA GPU metrics to an existing system snapshot."""
        try:
            utilization = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
            memory_info = pynvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
            gpu_temperature = pynvml.nvmlDeviceGetTemperature(
                self._gpu_handle,
                pynvml.NVML_TEMPERATURE_GPU,
            )

            gpu_memory_percent = memory_info.used / memory_info.total * 100 if memory_info.total else 0.0

            return SystemMetrics(
                cpu_percent=metrics.cpu_percent,
                process_threads=metrics.process_threads,
                cpu_temperature=metrics.cpu_temperature,
                memory_percent=metrics.memory_percent,
                memory_used_gb=metrics.memory_used_gb,
                memory_total_gb=metrics.memory_total_gb,
                gpu_available=True,
                gpu_utilization=float(utilization.gpu),
                gpu_memory_percent=gpu_memory_percent,
                gpu_memory_used_gb=memory_info.used * BYTES_TO_GB,
                gpu_memory_total_gb=memory_info.total * BYTES_TO_GB,
                gpu_temperature=float(gpu_temperature),
            )
        except Exception:
            return metrics

    def close(self) -> None:
        """Gracefully release hardware resources and stop tracking."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._nvml_initialized and pynvml is not None:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass

            self._nvml_initialized = False

    def __del__(self) -> None:
        """Defensive safety destructor helper."""
        try:
            self.close()
        except Exception:
            pass
