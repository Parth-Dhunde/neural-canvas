"""Tests for retrying failed pipeline stages."""

from __future__ import annotations

from app.pipeline.runnable import next_runnable_stage_id, stage_is_runnable


def _document(*stage_statuses: str) -> dict:
    names = [
        "Upload",
        "Background Removal",
        "Camera Estimation",
        "Reconstruction",
        "Mesh Generation",
        "Mesh Cleanup",
        "Export",
    ]
    stages = [
        {
            "id": index + 1,
            "name": name,
            "status": status,
            "progress": 100 if status == "completed" else 0,
            "completed_at": None,
        }
        for index, (name, status) in enumerate(zip(names, stage_statuses))
    ]
    return {"execution": {"status": "idle"}, "stages": stages}


def test_failed_camera_estimation_can_retry_when_prerequisites_complete() -> None:
    document = _document(
        "completed",
        "completed",
        "failed",
        "waiting",
        "waiting",
        "waiting",
        "waiting",
    )

    ok, reason = stage_is_runnable(document, 3)
    assert ok is True
    assert reason == ""
    assert next_runnable_stage_id(document) == 3


def test_failed_camera_estimation_cannot_retry_without_background_removal() -> None:
    document = _document(
        "completed",
        "failed",
        "failed",
        "waiting",
        "waiting",
        "waiting",
        "waiting",
    )

    ok, reason = stage_is_runnable(document, 3)
    assert ok is False
    assert "Stage 2 must be completed" in reason


def test_completed_stage_cannot_rerun() -> None:
    document = _document(
        "completed",
        "completed",
        "completed",
        "waiting",
        "waiting",
        "waiting",
        "waiting",
    )

    ok, reason = stage_is_runnable(document, 3)
    assert ok is False
    assert "already completed" in reason
