"""Read-only job summaries: lifecycle, timings, training metrics and output availability.

Everything here is derived from records already on disk (``metadata.json``,
``pipeline.json``, ``instant_ngp/training.log``) and never writes to a job directory, so
older jobs, including protected ones, are summarised without being modified.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.engines.instant_ngp.training_metrics import count_checkpoints, parse_training_log
from app.jobs.lifecycle import derive_lifecycle, pipeline_duration_seconds, seconds_between
from app.jobs.pipeline_repository import PipelineRepository
from app.jobs.repository import JobRepository
from app.jobs.structure import (
    instant_ngp_output_path,
    instant_ngp_training_log_path,
)
from app.models.job import Job
from app.pipeline.constants import PIPELINE_STAGE_DEFINITIONS, TRAINING_STAGE_ID
from app.pipeline.pipeline_manager import PipelineManager


def load_pipeline_document(repository: PipelineRepository, job_id: str) -> dict[str, Any] | None:
    """Load ``pipeline.json`` without creating it (``PipelineState.load`` would)."""
    try:
        return repository.load(job_id)
    except (OSError, ValueError):
        return None


def _stages(document: dict[str, Any] | None) -> list[dict[str, Any]]:
    by_id = {stage["id"]: stage for stage in (document or {}).get("stages", []) if "id" in stage}
    stages = []
    for stage_id, name in PIPELINE_STAGE_DEFINITIONS:
        stage = by_id.get(stage_id) or {}
        stages.append(
            {
                "id": stage_id,
                "name": name,
                "status": str(stage.get("status", "waiting")),
                "progress": int(stage.get("progress", 0) or 0),
                "started_at": stage.get("started_at"),
                "completed_at": stage.get("completed_at"),
            }
        )
    return stages


def _training_metrics(job: Job, jobs_root: Path, stage4_completed: bool) -> dict[str, Any] | None:
    """Metrics recorded by Stage 4, else a read-only backfill from the job's training log."""
    if job.training_metrics:
        return dict(job.training_metrics)
    if not stage4_completed:
        return None
    parsed = parse_training_log(instant_ngp_training_log_path(jobs_root, job.id))
    if parsed is None:
        return None
    return {
        **parsed,
        "checkpoint_count": count_checkpoints(instant_ngp_output_path(jobs_root, job.id)),
        # GPU memory is not written to the training log, so older jobs cannot report it.
        "peak_vram_mib": None,
        "source": "training_log",
    }


def build_job_summary(
    job: Job,
    jobs_root: Path,
    pipeline_repository: PipelineRepository | None = None,
) -> dict[str, Any]:
    """Return the derived lifecycle and metric fields for ``job``."""
    repository = pipeline_repository or PipelineRepository()
    document = load_pipeline_document(repository, job.id)

    execution_status = str(((document or {}).get("execution") or {}).get("status", "idle"))
    interrupted = execution_status == "running" and not PipelineManager.is_running(job.id)
    if interrupted:
        # A run marked running that no request is executing was cut off by a restart.
        document = {**(document or {}), "execution": {"status": "idle"}}

    lifecycle = derive_lifecycle(
        document, fallback_status=job.status, fallback_progress=job.progress
    )
    stages = _stages(document) if document else []
    stage4 = next((stage for stage in stages if stage["id"] == TRAINING_STAGE_ID), None)
    stage4_completed = stage4 is not None and stage4["status"] == "completed"

    training_duration = (
        seconds_between(job.reconstruction_started_at, job.reconstruction_completed_at)
        if stage4_completed
        else None
    )
    available = (job.exports or {}).get("available") or {}
    failed_stage = next((stage for stage in stages if stage["status"] == "failed"), None)
    last_error = ((document or {}).get("execution") or {}).get("last_error")

    return {
        "job_type": job.job_type,
        "status": lifecycle.status,
        "progress": lifecycle.progress,
        "interrupted": interrupted,
        # Why the job stopped: the failing stage and the error persisted in pipeline.json.
        "failed_stage": (
            {"id": failed_stage["id"], "name": failed_stage["name"]} if failed_stage else None
        ),
        "last_error": last_error if lifecycle.status != "completed" else None,
        "stages": stages,
        "started_at": job.started_at,
        "completed_at": lifecycle.completed_at or (
            job.completed_at if lifecycle.status == "completed" else None
        ),
        "training_duration_seconds": training_duration,
        "pipeline_duration_seconds": pipeline_duration_seconds(document),
        "training_metrics": _training_metrics(job, jobs_root, stage4_completed),
        # The production pipeline does not evaluate PSNR; see the dashboard summary.
        "psnr_db": None,
        "outputs": {
            "mesh": bool(job.mesh_path),
            "cleaned_mesh": (job.mesh_cleanup or {}).get("status") == "succeeded",
            "exports": {variant: list(formats) for variant, formats in available.items()},
        },
    }


def summarize_job(job: Job, repository: JobRepository) -> dict[str, Any]:
    """``build_job_summary`` using the job repository's settings."""
    return build_job_summary(
        job, repository.jobs_root, PipelineRepository(repository.settings)
    )
