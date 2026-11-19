"""Dashboard summary statistics computed from job records.

Every value has one defined source; values without a valid measurement are reported as
``None`` with ``sample_size`` 0 instead of a placeholder. Experiment results under
``outputs/experiments`` are reported separately and never enter production statistics.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.jobs.lifecycle import ACTIVE_STATUSES, parse_iso
from app.jobs.pipeline_repository import PipelineRepository
from app.jobs.repository import JobRepository
from app.services.job_summary import build_job_summary

COMPLETED_WINDOW = timedelta(days=7)
STORAGE_CACHE_SECONDS = 30.0


def _valid(value: Any) -> float | None:
    """Return a positive finite number, else ``None``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value <= 0:
        return None
    return float(value)


def median_statistic(values: list[Any], *, unit: str, unavailable_reason: str) -> dict[str, Any]:
    """Median over valid measurements, with the sample size it was computed from."""
    valid = [number for number in (_valid(value) for value in values) if number is not None]
    if not valid:
        return {
            "statistic": "median",
            "value": None,
            "unit": unit,
            "sample_size": 0,
            "unavailable_reason": unavailable_reason,
        }
    return {
        "statistic": "median",
        "value": statistics.median(valid),
        "unit": unit,
        "sample_size": len(valid),
        "unavailable_reason": None,
    }


_storage_cache: dict[str, tuple[float, int]] = {}
_storage_lock = threading.Lock()


def directory_size_bytes(root: Path, *, max_age: float = STORAGE_CACHE_SECONDS) -> int:
    """Total size of regular files under ``root`` (symlinks not followed), cached briefly."""
    key = str(root)
    now = time.monotonic()
    with _storage_lock:
        cached = _storage_cache.get(key)
        if cached is not None and now - cached[0] < max_age:
            return cached[1]

    total = 0
    if root.is_dir():
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                try:
                    stat = os.lstat(os.path.join(dirpath, name))
                except OSError:
                    continue
                if not os.path.islink(os.path.join(dirpath, name)):
                    total += stat.st_size

    with _storage_lock:
        _storage_cache[key] = (now, total)
    return total


def experimental_benchmarks(outputs_root: Path) -> list[dict[str, Any]]:
    """Read experiment ``metrics.json`` records, labelled as experimental, read-only."""
    experiments_root = outputs_root / "experiments"
    if not experiments_root.is_dir():
        return []

    results: list[dict[str, Any]] = []
    for path in sorted(experiments_root.glob("*/*/metrics.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        name = data.get("experiment")
        if not isinstance(name, str) or not isinstance(data.get("psnr"), dict):
            continue
        # Experiment records key their own PSNR by the short id, e.g. "E4" for "E4_...".
        own = data["psnr"].get(name.split("_")[0]) or {}
        # "baseline" is the experiment's own evaluation of the production snapshot it compares
        # against; it is an experimental measurement, not a production statistic.
        baseline = data["psnr"].get("baseline") or {}
        training = data.get("training") or {}
        results.append(
            {
                "experiment": name,
                "group": path.parent.parent.name,
                "record": str(path.relative_to(outputs_root.parent)),
                "status": data.get("status"),
                "psnr_mean_db": _valid(own.get("psnr_mean")),
                "frames_evaluated": own.get("frames_evaluated"),
                "baseline_psnr_mean_db": _valid(baseline.get("psnr_mean")),
                "training_seconds": _valid(training.get("seconds")),
                "peak_vram_mib": _valid(training.get("gpu_used_mib_peak")),
                "final_loss": _valid(training.get("final_logged_loss")),
            }
        )
    return results


def build_dashboard_summary(
    settings: Settings | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    repository = JobRepository(settings=cfg)
    pipeline_repository = PipelineRepository(cfg)
    current = now or datetime.now(timezone.utc)

    summaries = [
        (job, build_job_summary(job, repository.jobs_root, pipeline_repository))
        for job in repository.list_all()
    ]

    completed = [(job, s) for job, s in summaries if s["status"] == "completed"]
    completed_7d = 0
    for _job, summary in completed:
        finished = parse_iso(summary["completed_at"])
        if finished is not None and finished.tzinfo is None:
            finished = finished.replace(tzinfo=timezone.utc)
        if finished is not None and current - finished <= COMPLETED_WINDOW:
            completed_7d += 1

    engines: dict[str, Any] = {}
    for engine in sorted({job.engine for job, _ in summaries}):
        engine_done = [(job, s) for job, s in completed if job.engine == engine]
        metrics = [s["training_metrics"] or {} for _job, s in engine_done]
        engines[engine] = {
            "completed_jobs": len(engine_done),
            "median_psnr_db": median_statistic(
                [s["psnr_db"] for _job, s in engine_done],
                unit="dB",
                unavailable_reason="The production pipeline does not evaluate PSNR.",
            ),
            "median_training_seconds": median_statistic(
                [s["training_duration_seconds"] for _job, s in engine_done],
                unit="s",
                unavailable_reason="No completed job has recorded training start and end times.",
            ),
            "median_peak_vram_mib": median_statistic(
                [m.get("peak_vram_mib") for m in metrics],
                unit="MiB",
                unavailable_reason=(
                    "Peak VRAM is recorded for training runs from this version on; "
                    "older training logs do not contain it."
                ),
            ),
        }

    return {
        "generated_at": current.isoformat(),
        "jobs": {
            "total": len(summaries),
            "active": sum(1 for _job, s in summaries if s["status"] in ACTIVE_STATUSES),
            "active_statuses": sorted(ACTIVE_STATUSES),
            "completed_total": len(completed),
            "completed_7d": completed_7d,
            "failed": sum(1 for _job, s in summaries if s["status"] == "failed"),
        },
        "training": median_statistic(
            [s["training_duration_seconds"] for _job, s in completed],
            unit="s",
            unavailable_reason="No completed job has recorded training start and end times.",
        ),
        "storage": {
            "bytes": directory_size_bytes(repository.jobs_root),
            "scope": "jobs/ (uploads, masks, COLMAP, snapshots, meshes, exports)",
        },
        "engines": engines,
        "experimental": experimental_benchmarks(cfg.outputs_path),
    }
