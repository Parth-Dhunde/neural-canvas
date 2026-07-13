"""Mesh generation orchestration for pipeline jobs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

from app.engines.mesh_generation.base import MeshGenerationEngine, MeshGenerationResult
from app.engines.mesh_generation.factory import get_mesh_generation_engine
from app.jobs.repository import JobRepository
from app.jobs.structure import job_root_path
from app.models.job import Job, utc_now_iso


class MeshGenerationError(Exception):
    """Raised when mesh generation cannot start or complete."""


class MeshGenerationService:
    """Generate meshes for a job using a pluggable engine."""

    def __init__(
        self,
        repository: JobRepository | None = None,
        engine: MeshGenerationEngine | None = None,
    ) -> None:
        self._repository = repository or JobRepository()
        self._engine = engine

    def _engine_for(self, job: Job) -> MeshGenerationEngine:
        return self._engine or get_mesh_generation_engine(job)

    def validate(self, job_id: str) -> MeshGenerationResult:
        job = self._require_job(job_id)
        return self._engine_for(job).validate(job)

    async def generate_mesh(
        self,
        job_id: str,
        *,
        log: Callable[[str, str], None] | Callable[[str], None] | None = None,
        on_progress: Callable[[int], None] | None = None,
        check_control: Callable[[], None] | None = None,
    ) -> dict[str, object]:
        """Run mesh generation and persist job metadata."""
        job = self._require_job(job_id)
        engine = self._engine_for(job)

        validation = engine.validate(job)
        if not validation.success:
            raise MeshGenerationError(validation.message)

        result = await asyncio.to_thread(
            engine.generate,
            job,
            log=log,
            on_progress=on_progress,
            check_control=check_control,
        )
        if not result.success:
            raise MeshGenerationError(result.message)

        mesh_glb = str(result.data.get("mesh_glb") or "")
        mesh_dir = str(result.data.get("mesh_dir") or "")
        vertex_count = int(result.data.get("vertex_count") or 0)
        triangle_count = int(result.data.get("triangle_count") or 0)

        job_root = job_root_path(self._repository.jobs_root, job_id)
        mesh_path = _relative_to_job_root(job_root, mesh_glb) if mesh_glb else None

        generated_at = utc_now_iso()
        self._repository.update(
            job_id,
            mesh_generated_at=generated_at,
            mesh_path=mesh_path,
            mesh_formats=["obj", "ply", "glb"],
            vertex_count=vertex_count,
            triangle_count=triangle_count,
        )

        return {
            "job_id": job_id,
            "engine": job.engine,
            "mesh_generated_at": generated_at,
            "mesh_path": mesh_path,
            "mesh_dir": mesh_dir,
            "mesh_formats": ["obj", "ply", "glb"],
            "vertex_count": vertex_count,
            "triangle_count": triangle_count,
        }

    def cancel(self, job_id: str) -> MeshGenerationResult:
        job = self._require_job(job_id)
        return self._engine_for(job).cancel(job)

    def _require_job(self, job_id: str) -> Job:
        job = self._repository.get(job_id)
        if job is None:
            raise MeshGenerationError(f"Job not found: {job_id}")
        return job


def _relative_to_job_root(job_root: Path, absolute_path: str) -> str:
    # Persist job-relative paths only.
    path = Path(absolute_path)
    try:
        return str(path.relative_to(job_root))
    except ValueError:
        # If engine returned a relative path already, accept it.
        return str(path)


def get_mesh_generation_service() -> MeshGenerationService:
    """FastAPI dependency that returns a mesh generation service instance."""
    return MeshGenerationService()

