"""Mesh cleanup orchestration for pipeline jobs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from app.engines.mesh_cleanup import get_mesh_cleanup_engine
from app.engines.mesh_cleanup.base import MeshCleanupEngine, MeshCleanupResult
from app.jobs.repository import JobRepository
from app.models.job import Job, utc_now_iso


class MeshCleanupError(Exception):
    """Raised when mesh cleanup cannot start or complete."""


def cleanup_summary(report: dict[str, Any]) -> dict[str, Any]:
    """Compact metadata view of a cleanup report (full report lives in cleanup.json)."""
    return {
        "status": report["status"],
        "cleanup_id": report["cleanup_id"],
        "completed_at": report["completed_at"],
        "source": report["source"],
        "output": report["output"],
        "report_path": f"{report['output']['dir']}/cleanup.json",
        "parameters": report["parameters"],
        "decimation": report["steps"].get("decimation"),
        "smoothing": report["steps"].get("smoothing"),
        "removed": {
            **report["steps"].get("repair", {}),
            **report["steps"].get("floaters", {}),
        },
        "output_validation": {
            key: report["validation"]["output"].get(key)
            for key in ("usable", "watertight", "winding_consistent", "components", "problems")
        },
        "warnings": report["warnings"],
    }


class MeshCleanupService:
    """Run mesh cleanup for a job and persist the outcome in job metadata."""

    def __init__(
        self,
        repository: JobRepository | None = None,
        engine: MeshCleanupEngine | None = None,
    ) -> None:
        self._repository = repository or JobRepository()
        self._engine = engine or get_mesh_cleanup_engine()

    def validate(self, job_id: str) -> MeshCleanupResult:
        return self._engine.validate(self._require_job(job_id))

    async def clean(
        self,
        job_id: str,
        *,
        log: Callable[[str, str], None] | Callable[[str], None] | None = None,
        on_progress: Callable[[int], None] | None = None,
        check_control: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        job = self._require_job(job_id)
        result = await asyncio.to_thread(
            self._engine.clean,
            job,
            log=log,
            on_progress=on_progress,
            check_control=check_control,
        )
        if not result.success:
            # Record the failure so an older successful cleanup is not mistaken for this run;
            # export selection only uses cleanups whose status is "succeeded". The previous
            # success (whose files are never deleted) stays referenced for inspection/recovery.
            previous = job.mesh_cleanup or {}
            previous_success = (
                previous if previous.get("status") == "succeeded" else previous.get("previous_success")
            )
            self._repository.update(
                job_id,
                mesh_cleanup={
                    "status": "failed",
                    "failed_at": utc_now_iso(),
                    "error": result.message,
                    "error_code": result.error_code,
                    "source_mesh_path": job.mesh_path,
                    "previous_success": previous_success,
                },
            )
            raise MeshCleanupError(result.message)

        summary = cleanup_summary(result.data)
        self._repository.update(job_id, mesh_cleanup=summary)
        return {"job_id": job_id, **summary}

    def _require_job(self, job_id: str) -> Job:
        job = self._repository.get(job_id)
        if job is None:
            raise MeshCleanupError(f"Job not found: {job_id}")
        return job
