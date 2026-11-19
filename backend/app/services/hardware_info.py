"""Local host hardware telemetry for API responses."""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class HardwareSummary:
    status: str
    gpu: str
    driver: str
    cuda: str
    memory: str
    temperature: str

    def to_api_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "gpu": self.gpu,
            "driver": self.driver,
            "cuda": self.cuda,
            "memory": self.memory,
            "temperature": self.temperature,
        }


def collect_hardware_summary() -> HardwareSummary:
    """Collect live GPU/CPU/RAM telemetry from the local machine."""
    gpu_name = "N/A"
    gpu_util = "N/A"
    gpu_temp = "N/A"
    vram_used = "N/A"
    vram_total = "N/A"
    driver = "N/A"
    cuda = "N/A"

    if shutil.which("nvidia-smi"):
        (
            gpu_name,
            gpu_util,
            gpu_temp,
            vram_used,
            vram_total,
            driver,
        ) = _query_nvidia_smi()
        cuda = _query_cuda_version() or "N/A"

    cpu_util = _query_cpu_utilization()
    cpu_temp = _query_cpu_temperature()
    ram_used, ram_total = _query_system_ram()

    status = _format_status(cpu_util, gpu_util)
    gpu = _format_gpu(gpu_name, gpu_util, vram_used, vram_total)
    memory = _format_memory(ram_used, ram_total, vram_used, vram_total)
    temperature = _format_temperature(gpu_temp, cpu_temp)

    return HardwareSummary(
        status=status,
        gpu=gpu,
        driver=driver,
        cuda=cuda,
        memory=memory,
        temperature=temperature,
    )


def _format_status(cpu_util: str, gpu_util: str) -> str:
    if cpu_util != "N/A" and gpu_util != "N/A":
        return f"CPU {cpu_util} · GPU {gpu_util}"
    if gpu_util != "N/A":
        return f"GPU {gpu_util}"
    if cpu_util != "N/A":
        return f"CPU {cpu_util}"
    return "N/A"


def _format_gpu(name: str, util: str, vram_used: str, vram_total: str) -> str:
    if name == "N/A":
        return "N/A"
    if util != "N/A" and vram_used != "N/A" and vram_total != "N/A":
        return f"{name} · {util} · VRAM {vram_used}/{vram_total} GB"
    if util != "N/A":
        return f"{name} · {util}"
    return name


def _format_memory(ram_used: str, ram_total: str, vram_used: str, vram_total: str) -> str:
    ram_part = "N/A"
    if ram_used != "N/A" and ram_total != "N/A":
        ram_part = f"{ram_used}/{ram_total} GB RAM"
    vram_part = "N/A"
    if vram_used != "N/A" and vram_total != "N/A":
        vram_part = f"{vram_used}/{vram_total} GB VRAM"
    if ram_part != "N/A" and vram_part != "N/A":
        return f"{ram_part} · {vram_part}"
    return ram_part if ram_part != "N/A" else vram_part


def _format_temperature(gpu_temp: str, cpu_temp: str) -> str:
    parts: list[str] = []
    if gpu_temp != "N/A":
        parts.append(f"GPU {gpu_temp}")
    if cpu_temp != "N/A":
        parts.append(f"CPU {cpu_temp}")
    return " · ".join(parts) if parts else "N/A"


def _query_nvidia_smi() -> tuple[str, str, str, str, str, str]:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ("N/A",) * 6

    if completed.returncode != 0:
        return ("N/A",) * 6

    line = completed.stdout.strip().splitlines()[0] if completed.stdout.strip() else ""
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 6:
        return ("N/A",) * 6

    name = parts[0] or "N/A"
    util = f"{parts[1]}%" if parts[1] and parts[1].lower() != "n/a" else "N/A"
    temp = f"{parts[2]}°C" if parts[2] and parts[2].lower() != "n/a" else "N/A"
    try:
        vram_used = f"{max(0, round(int(float(parts[3])) / 1024, 1))}"
        vram_total = f"{max(1, round(int(float(parts[4])) / 1024, 1))}"
    except ValueError:
        vram_used = "N/A"
        vram_total = "N/A"
    driver = parts[5] or "N/A"
    return name, util, temp, vram_used, vram_total, driver


def _query_cuda_version() -> str | None:
    try:
        completed = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if completed.returncode != 0:
        return None

    match = re.search(r"CUDA UMD Version:\s*([\d.]+)", completed.stdout)
    if match:
        return match.group(1)

    match = re.search(r"CUDA Version:\s*([\d.]+)", completed.stdout)
    return match.group(1) if match else None


def _query_system_ram() -> tuple[str, str]:
    try:
        meminfo = _read_meminfo()
        total_kb = meminfo.get("MemTotal", 0)
        available_kb = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
        if total_kb <= 0:
            return "N/A", "N/A"
        used_kb = max(0, total_kb - available_kb)
        return (
            f"{used_kb / (1024 * 1024):.1f}",
            f"{total_kb / (1024 * 1024):.1f}",
        )
    except OSError:
        return "N/A", "N/A"


def _read_meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    with open("/proc/meminfo", encoding="utf-8") as handle:
        for line in handle:
            key, _, raw = line.partition(":")
            if not raw:
                continue
            number = raw.strip().split()[0]
            if number.isdigit():
                values[key] = int(number)
    return values


def _query_cpu_utilization() -> str:
    first = _read_cpu_jiffies()
    if first is None:
        return "N/A"
    time.sleep(0.15)
    second = _read_cpu_jiffies()
    if second is None:
        return "N/A"

    idle_delta = second[0] - first[0]
    total_delta = second[1] - first[1]
    if total_delta <= 0:
        return "N/A"
    usage = max(0.0, min(100.0, (1.0 - idle_delta / total_delta) * 100.0))
    return f"{usage:.0f}%"


def _read_cpu_jiffies() -> tuple[int, int] | None:
    try:
        with open("/proc/stat", encoding="utf-8") as handle:
            line = handle.readline()
    except OSError:
        return None

    if not line.startswith("cpu "):
        return None

    parts = line.split()[1:]
    if len(parts) < 4:
        return None

    try:
        values = [int(value) for value in parts]
    except ValueError:
        return None

    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values)
    return idle, total


def _query_cpu_temperature() -> str:
    candidates: list[float] = []

    for path in sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp")):
        zone_dir = os.path.dirname(path)
        zone_type_path = os.path.join(zone_dir, "type")
        try:
            with open(zone_type_path, encoding="utf-8") as handle:
                zone_type = handle.read().strip().lower()
            with open(path, encoding="utf-8") as handle:
                milli = int(handle.read().strip())
        except (OSError, ValueError):
            continue

        celsius = milli / 1000.0
        if "cpu" in zone_type or "x86" in zone_type or "pkg" in zone_type:
            return f"{celsius:.0f}°C"
        candidates.append(celsius)

    if candidates:
        return f"{max(candidates):.0f}°C"
    return "N/A"
