"""Training metrics parsed from Instant-NGP's tqdm progress output.

``scripts/run.py`` reports progress as a tqdm bar, e.g.
``Training: 42%|####| 14700/35000 [10:02<13:51, 24.4steps/s, loss=0.016]``. The same parser
serves the live stage (fed line by line) and the read-only backfill of older ``training.log``
files. Only values that appear in the output are reported: the bar has steps, elapsed time,
step rate and loss, but no ray throughput or GPU memory.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.text import strip_ansi

_BAR_RE = re.compile(
    r"(?P<step>\d+)/(?P<total>\d+) \[(?P<elapsed>[0-9:]+)<[^,\]]*"
    r"(?:,\s*(?P<rate>[0-9.]+|\?)(?P<unit>steps/s|s/steps?))?"
    r"(?:,\s*loss=(?P<loss>[0-9.eE+-]+))?"
)
_SNAPSHOT_SAVED_RE = re.compile(r"Saved snapshot")


def parse_tqdm_elapsed(text: str) -> int | None:
    """Return seconds for a tqdm elapsed field such as ``21:07`` or ``1:02:03``."""
    try:
        parts = [int(part) for part in text.split(":")]
    except ValueError:
        return None
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + part
    return seconds


@dataclass
class TrainingMetricsTracker:
    """Accumulate the latest training values from progress lines."""

    steps_completed: int | None = None
    total_steps: int | None = None
    elapsed_seconds: int | None = None
    last_steps_per_second: float | None = None
    final_loss: float | None = None
    snapshots_saved: int = 0

    def observe(self, line: str) -> None:
        text = strip_ansi(line)
        if _SNAPSHOT_SAVED_RE.search(text):
            self.snapshots_saved += 1
        match = None
        for match in _BAR_RE.finditer(text):
            pass
        if match is None:
            return

        self.steps_completed = int(match.group("step"))
        self.total_steps = int(match.group("total"))
        elapsed = parse_tqdm_elapsed(match.group("elapsed"))
        if elapsed is not None:
            self.elapsed_seconds = elapsed
        rate = match.group("rate")
        if rate and rate != "?":
            value = float(rate)
            if match.group("unit").startswith("s/"):
                value = 1.0 / value if value > 0 else 0.0
            if value > 0:
                self.last_steps_per_second = value
        loss = match.group("loss")
        if loss is not None:
            try:
                self.final_loss = float(loss)
            except ValueError:
                pass

    @property
    def has_data(self) -> bool:
        return self.steps_completed is not None

    def mean_steps_per_second(self) -> float | None:
        if not self.steps_completed or not self.elapsed_seconds:
            return None
        return self.steps_completed / self.elapsed_seconds

    def to_dict(self) -> dict[str, Any]:
        mean_rate = self.mean_steps_per_second()
        return {
            "final_loss": self.final_loss,
            "last_logged_step": self.steps_completed,
            "total_steps": self.total_steps,
            "tqdm_elapsed_seconds": self.elapsed_seconds,
            "mean_steps_per_second": round(mean_rate, 3) if mean_rate is not None else None,
            "last_steps_per_second": self.last_steps_per_second,
            "snapshots_saved": self.snapshots_saved,
        }


def count_checkpoints(instant_ngp_dir: Path) -> int:
    """Count saved Instant-NGP snapshots (``*.msgpack``) under the job's output directory."""
    if not instant_ngp_dir.is_dir():
        return 0
    return sum(1 for path in instant_ngp_dir.rglob("*.msgpack") if path.is_file())


_log_cache: dict[str, tuple[tuple[int, int], dict[str, Any] | None]] = {}
_log_cache_lock = threading.Lock()


def parse_training_log(path: Path) -> dict[str, Any] | None:
    """Parse a finished ``training.log`` read-only; ``None`` when it holds no progress bar.

    Results are cached by file size and mtime, so dashboards polling old jobs parse each
    log once per process.
    """
    try:
        stat = path.stat()
    except OSError:
        return None
    key = str(path)
    signature = (stat.st_size, stat.st_mtime_ns)
    with _log_cache_lock:
        cached = _log_cache.get(key)
        if cached is not None and cached[0] == signature:
            return cached[1]

    tracker = TrainingMetricsTracker()
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        # tqdm redraws with carriage returns; treat them as line breaks.
        for raw in handle:
            for line in raw.replace("\r", "\n").split("\n"):
                if line:
                    tracker.observe(line)
    result = tracker.to_dict() if tracker.has_data else None

    with _log_cache_lock:
        _log_cache[key] = (signature, result)
    return result

