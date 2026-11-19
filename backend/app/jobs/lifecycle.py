"""Derive a job's overall lifecycle from its pipeline document.

``pipeline.json`` is the source of truth for stage progress. The job-level ``status`` and
``progress`` in ``metadata.json`` are a persisted copy of what this module derives, written by
the pipeline manager; jobs created before that existed only have the stale defaults
(``waiting``/0), so readers derive the lifecycle instead of trusting the stored copy.

Lifecycle values (shared with the frontend ``JobStatus`` type):

- ``waiting``   — not finished and nothing running (new, or stopped between stages)
- ``queued``    — reserved; the backend has no queue yet
- ``running``   — a pipeline run is executing
- ``paused``    — a run was paused
- ``cancelled`` — the last run was cancelled
- ``failed``    — a stage failed and has not been retried successfully
- ``completed`` — every stage completed
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

ACTIVE_STATUSES = frozenset({"queued", "running"})
TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})


@dataclass(frozen=True)
class JobLifecycle:
    status: str
    progress: int
    completed_at: str | None


def parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def seconds_between(start: Any, end: Any) -> float | None:
    """Return ``end - start`` in seconds, or ``None`` when either is missing or out of order."""
    begin, finish = parse_iso(start), parse_iso(end)
    if begin is None or finish is None:
        return None
    seconds = (finish - begin).total_seconds()
    return seconds if seconds >= 0 else None


def _stage_progress(stage: dict[str, Any]) -> int:
    status = str(stage.get("status", "waiting"))
    if status == "completed":
        return 100
    if status in {"running", "failed"}:
        try:
            return max(0, min(100, int(stage.get("progress", 0))))
        except (TypeError, ValueError):
            return 0
    return 0


def derive_lifecycle(
    document: dict[str, Any] | None,
    *,
    fallback_status: str = "waiting",
    fallback_progress: int = 0,
) -> JobLifecycle:
    """Return the overall status/progress for a pipeline document (``None`` → fallbacks)."""
    stages = [stage for stage in (document or {}).get("stages", []) if "id" in stage]
    if not stages:
        return JobLifecycle(fallback_status, fallback_progress, None)

    statuses = [str(stage.get("status", "waiting")) for stage in stages]
    execution = str(((document or {}).get("execution") or {}).get("status", "idle"))
    progress = round(sum(_stage_progress(stage) for stage in stages) / len(stages))

    if all(status == "completed" for status in statuses):
        completed = [parse_iso(stage.get("completed_at")) for stage in stages]
        known = [value for value in completed if value is not None]
        completed_at = max(known).isoformat() if known else None
        return JobLifecycle("completed", 100, completed_at)

    if execution == "running":
        status = "running"
    elif execution == "paused":
        status = "paused"
    elif "failed" in statuses:
        status = "failed"
    elif execution == "cancelled":
        status = "cancelled"
    else:
        status = "waiting"
    return JobLifecycle(status, min(progress, 99), None)


def pipeline_duration_seconds(document: dict[str, Any] | None) -> float | None:
    """Sum of stage run times, when every completed stage recorded ``started_at``.

    Wall-clock time from creation to completion would include days of idle time between
    stages, so only measured stage runs are summed. Older jobs have no stage start times.
    """
    stages = [stage for stage in (document or {}).get("stages", []) if "id" in stage]
    completed = [stage for stage in stages if stage.get("status") == "completed"]
    if not completed:
        return None
    total = 0.0
    for stage in completed:
        seconds = seconds_between(stage.get("started_at"), stage.get("completed_at"))
        if seconds is None:
            return None
        total += seconds
    return total
