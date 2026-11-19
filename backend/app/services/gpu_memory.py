"""Sample a process's GPU memory while it runs, to record its peak VRAM.

``nvidia-smi --query-compute-apps`` reports per-process memory. Sampling is best effort:
any failure leaves the peak as ``None`` (reported as unavailable) and never affects the
process being measured.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
from collections.abc import Callable

from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_INTERVAL_SECONDS = 2.0


def query_process_gpu_memory_mib() -> dict[int, int] | None:
    """Return ``{pid: used MiB}`` for GPU compute processes, or ``None`` if unavailable."""
    if shutil.which("nvidia-smi") is None:
        return None
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,used_memory",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None

    usage: dict[int, int] = {}
    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 2:
            continue
        try:
            usage[int(parts[0])] = int(float(parts[1]))
        except ValueError:
            continue
    return usage


class PeakGpuMemorySampler:
    """Background thread tracking the peak GPU memory of the process ``pid_getter`` names."""

    def __init__(
        self,
        pid_getter: Callable[[], int | None],
        *,
        interval: float = DEFAULT_INTERVAL_SECONDS,
        query: Callable[[], dict[int, int] | None] = query_process_gpu_memory_mib,
    ) -> None:
        self._pid_getter = pid_getter
        self._interval = interval
        self._query = query
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.peak_mib: int | None = None
        self.samples = 0

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="gpu-memory-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> int | None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self._interval + 6)
        return self.peak_mib

    def sample_once(self) -> None:
        pid = self._pid_getter()
        if pid is None:
            return
        usage = self._query()
        if not usage or pid not in usage:
            return
        self.samples += 1
        value = usage[pid]
        if self.peak_mib is None or value > self.peak_mib:
            self.peak_mib = value

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.sample_once()
            except Exception:  # noqa: BLE001 - sampling must never break training
                logger.debug("GPU memory sample failed", exc_info=True)
            self._stop.wait(self._interval)
