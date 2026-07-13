"""Camera estimation orchestration for reconstruction jobs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from app.engines.camera_estimation import get_camera_estimation_engine
from app.engines.camera_estimation.base import CameraEstimationEngine, CameraEstimationResult
from app.jobs.repository import JobRepository
from app.models.job import Job, utc_now_iso


class CameraEstimationError(Exception):
    """Raised when camera estimation cannot start."""


class CameraEstimationService:
    """Run camera estimation for a job using a pluggable engine."""

    def __init__(
        self,
        repository: JobRepository | None = None,
        engine: CameraEstimationEngine | None = None,
    ) -> None:
        self._repository = repository or JobRepository()
        self._engine = engine or get_camera_estimation_engine()

    def validate(self, job_id: str) -> CameraEstimationResult:
        job = self._require_job(job_id)
        return self._engine.validate(job)

    async def estimate_cameras(
        self,
        job_id: str,
        *,
        log: Callable[[str, str], None] | Callable[[str], None] | None = None,
        on_progress: Callable[[int], None] | None = None,
        check_control: Callable[[], None] | None = None,
    ) -> dict[str, object]:
        """Estimate camera poses and persist job metadata."""
        job = self._require_job(job_id)
        validation = self._engine.validate(job)
        if not validation.success:
            raise CameraEstimationError(validation.message)

        result = await asyncio.to_thread(
            self._engine.estimate,
            job,
            log=log,
            on_progress=on_progress,
            check_control=check_control,
        )
        if not result.success:
            raise CameraEstimationError(result.message)

        self._repository.update(
            job_id,
            camera_estimated_at=utc_now_iso(),
            transforms_path=result.transforms_path,
            registered_image_count=result.registered_images,
        )

        return {
            "job_id": job_id,
            "transforms_path": result.transforms_path,
            "registered_images": result.registered_images,
            "error_code": result.error_code,
            **result.data,
        }

    def _require_job(self, job_id: str) -> Job:
        job = self._repository.get(job_id)
        if job is None:
            raise CameraEstimationError(f"Job not found: {job_id}")
        return job


def get_camera_estimation_service() -> CameraEstimationService:
    """FastAPI dependency that returns a camera estimation service instance."""
    return CameraEstimationService()
