"""Determine whether a pipeline stage can be executed or retried."""

from __future__ import annotations

from typing import Any

RUNNABLE_STATUSES = frozenset({"waiting", "queued", "failed"})


def stage_is_runnable(document: dict[str, Any], stage_id: int) -> tuple[bool, str]:
    """Return whether ``stage_id`` may run, including retries after failure."""
    stages = {stage["id"]: stage for stage in document.get("stages", []) if "id" in stage}
    stage = stages.get(stage_id)
    if stage is None:
        return False, f"Unknown stage id: {stage_id}"

    status = str(stage.get("status", "waiting"))
    if status == "completed":
        return False, f"Stage {stage_id} is already completed."
    if status == "running":
        return False, f"Stage {stage_id} is already running."
    if status not in RUNNABLE_STATUSES:
        return False, f"Stage {stage_id} cannot run from status '{status}'."

    for prereq_id in range(1, stage_id):
        prereq = stages.get(prereq_id)
        if prereq is None:
            continue
        if str(prereq.get("status")) != "completed":
            return False, f"Stage {prereq_id} must be completed before stage {stage_id} can run."

    return True, ""


def next_runnable_stage_id(document: dict[str, Any]) -> int | None:
    """Return the next incomplete stage id that can run, including failed stages."""
    stages = sorted(document.get("stages", []), key=lambda item: item["id"])
    for stage in stages:
        stage_id = int(stage["id"])
        if str(stage.get("status")) == "completed":
            continue
        ok, _ = stage_is_runnable(document, stage_id)
        if ok:
            return stage_id
        return None
    return None
