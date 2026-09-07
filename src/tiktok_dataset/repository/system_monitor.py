from __future__ import annotations

import shutil
import subprocess
import threading
import time
from dataclasses import dataclass

import psutil

try:
    import pynvml
except ImportError:
    pynvml = None

BYTES_TO_GB = 1 / (1024**3)


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
    def __init__(self) -> None:
        self.process = psutil.Process()
        self._nvml_initialized = False
        self._gpu_handle = None
        self._initialize_gpu()
        self.process.cpu_percent(interval=None)

        self._cpu_temp = 0.0
        self._running = True
        self._temp_thread = threading.Thread(target=self._update_temp_loop, daemon=True)
        self._temp_thread.start()

    def _initialize_gpu(self) -> None:
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
        powershell_path = shutil.which("powershell.exe")

        while self._running:
            try:
                temps = psutil.sensors_temperatures()
                for key in ["coretemp", "cpu_thermal", "k10temp"]:
                    if temps.get(key):
                        self._cpu_temp = float(temps[key][0].current)
                        break
            except Exception:
                pass

            if self._cpu_temp == 0.0 and powershell_path:
                try:
                    cmd = [
                        powershell_path,
                        "-NoProfile",
                        "-Command",
                        "(Get-Counter '\\Thermal Zone Information(*)\\Temperature').CounterSamples.CookedValue",
                    ]
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=2)
                    if result.returncode == 0 and result.stdout.strip():
                        raw_vals = [float(val) for val in result.stdout.strip().split() if val.replace(".", "", 1).isdigit()]
                        if raw_vals:
                            max_raw = max(raw_vals)
                            celsius = (max_raw / 10.0) - 273.15 if max_raw > 1000 else max_raw - 273.15
                            if 0 < celsius < 110:
                                self._cpu_temp = round(celsius, 1)
                except Exception:
                    pass

            time.sleep(5.0)

    def sample(self) -> SystemMetrics:
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=None)

        metrics = SystemMetrics(
            cpu_percent=min(cpu_percent, 100.0),
            process_threads=self.process.num_threads(),
            cpu_temperature=self._cpu_temp,
            memory_percent=memory.percent,
            memory_used_gb=memory.used * BYTES_TO_GB,
            memory_total_gb=memory.total * BYTES_TO_GB,
        )

        if not self._nvml_initialized:
            return metrics

        try:
            utilization = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
            memory_info = pynvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
            gpu_temperature = pynvml.nvmlDeviceGetTemperature(
                self._gpu_handle,
                pynvml.NVML_TEMPERATURE_GPU,
            )

            return SystemMetrics(
                cpu_percent=metrics.cpu_percent,
                process_threads=metrics.process_threads,
                cpu_temperature=metrics.cpu_temperature,
                memory_percent=metrics.memory_percent,
                memory_used_gb=metrics.memory_used_gb,
                memory_total_gb=metrics.memory_total_gb,
                gpu_available=True,
                gpu_utilization=float(utilization.gpu),
                gpu_memory_percent=memory_info.used / memory_info.total * 100 if memory_info.total else 0.0,
                gpu_memory_used_gb=memory_info.used * BYTES_TO_GB,
                gpu_memory_total_gb=memory_info.total * BYTES_TO_GB,
                gpu_temperature=float(gpu_temperature),
            )
        except Exception:
            return metrics

    def close(self) -> None:
        self._running = False
        if self._nvml_initialized:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
            self._nvml_initialized = False

    def __del__(self) -> None:
        self.close()
