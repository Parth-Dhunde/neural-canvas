"""Job lifecycle management."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.jobs.repository import JobRepository
from app.models.job import Job
from app.pipeline.pipeline_manager import PipelineManager


class JobManager(ABC):
    """Contract for managing reconstruction jobs."""

    @abstractmethod
    async def create_job(self, name: str | None, engine: str) -> Job:
        """Create a new job record and prepare its workspace."""

    @abstractmethod
    async def delete_job(self, job_id: str) -> None:
        """Remove a job and its workspace."""

    @abstractmethod
    async def get_job(self, job_id: str) -> Job | None:
        """Return a single job by identifier."""

    @abstractmethod
    async def update_status(self, job_id: str, status: str, **fields: Any) -> Job:
        """Update job status and optional metadata fields."""

    @abstractmethod
    async def list_jobs(self) -> list[Job]:
        """Return all known jobs."""

    @abstractmethod
    async def create_folder_structure(self, job_id: str) -> Path:
        """Create the on-disk directory layout for a job."""


class JobManagerImpl(JobManager):
    """Filesystem-backed job manager."""

    def __init__(self, repository: JobRepository | None = None) -> None:
        self._repository = repository or JobRepository()
        self._pipeline_manager = PipelineManager()

    @property
    def repository(self) -> JobRepository:
        return self._repository

    async def create_job(self, name: str | None, engine: str) -> Job:
        validated_engine = self._repository.validate_engine(engine)
        job_id = self._repository.next_job_id()
        self._repository.create_folder_structure(job_id)

        job = Job(
            id=job_id,
            name=name or self._repository.default_job_name(job_id),
            engine=validated_engine,
            status="waiting",
            progress=0,
        )
        saved = self._repository.save(job)
        self._pipeline_manager.initialize(job_id)
        return saved

    async def delete_job(self, job_id: str) -> None:
        from app.services.job_deletion import JobDeletionService

        await JobDeletionService(self._repository).delete(job_id)

    async def get_job(self, job_id: str) -> Job | None:
        return self._repository.get(job_id)

    async def update_status(self, job_id: str, status: str, **fields: Any) -> Job:
        updated = self._repository.update(job_id, status=status, **fields)
        if updated is None:
            raise KeyError(f"Job not found: {job_id}")
        return updated

    async def list_jobs(self) -> list[Job]:
        return self._repository.list_all()

    async def create_folder_structure(self, job_id: str) -> Path:
        return self._repository.create_folder_structure(job_id)


def get_job_manager() -> JobManagerImpl:
    """FastAPI dependency that returns a job manager instance."""
    return JobManagerImpl()
