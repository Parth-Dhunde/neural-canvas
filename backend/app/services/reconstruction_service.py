"""Reconstruction orchestration for pipeline jobs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from app.engines.reconstruction import get_reconstruction_engine
from app.engines.reconstruction.base import ReconstructionEngine, ReconstructionResult
from app.jobs.repository import JobRepository
from app.models.job import Job, utc_now_iso


class ReconstructionError(Exception):
    """Raised when reconstruction cannot start or complete."""


class ReconstructionService:
    """Run neural reconstruction for a job using a pluggable engine."""

    def __init__(
        self,
        repository: JobRepository | None = None,
        engine: ReconstructionEngine | None = None,
    ) -> None:
        self._repository = repository or JobRepository()
        self._engine = engine

    def _engine_for(self, job: Job) -> ReconstructionEngine:
        return self._engine or get_reconstruction_engine(job)

    def validate(self, job_id: str) -> ReconstructionResult:
        job = self._require_job(job_id)
        return self._engine_for(job).validate(job)

    async def run_reconstruction(
        self,
        job_id: str,
        *,
        log: Callable[[str, str], None] | Callable[[str], None] | None = None,
        on_progress: Callable[[int], None] | None = None,
        check_control: Callable[[], None] | None = None,
    ) -> dict[str, object]:
        """Run reconstruction and persist job metadata."""
        job = self._require_job(job_id)
        engine = self._engine_for(job)

        validation = engine.validate(job)
        if not validation.success:
            raise ReconstructionError(validation.message)

        started_at = utc_now_iso()
        self._repository.update(
            job_id,
            reconstruction_started_at=started_at,
            engine=job.engine,
        )

        result = await asyncio.to_thread(
            engine.run,
            job,
            log=log,
            on_progress=on_progress,
            check_control=check_control,
        )
        if not result.success:
            raise ReconstructionError(result.message)

        completed_at = utc_now_iso()
        self._repository.update(
            job_id,
            reconstruction_completed_at=completed_at,
            engine=job.engine,
            snapshot_path=result.snapshot_path,
        )

        return {
            "job_id": job_id,
            "engine": job.engine,
            "snapshot_path": result.snapshot_path,
            "reconstruction_started_at": started_at,
            "reconstruction_completed_at": completed_at,
            "error_code": result.error_code,
            **result.data,
        }

    def cancel(self, job_id: str) -> ReconstructionResult:
        job = self._require_job(job_id)
        return self._engine_for(job).cancel(job)

    def _require_job(self, job_id: str) -> Job:
        job = self._repository.get(job_id)
        if job is None:
            raise ReconstructionError(f"Job not found: {job_id}")
        return job


def get_reconstruction_service() -> ReconstructionService:
    """FastAPI dependency that returns a reconstruction service instance."""
    return ReconstructionService()
