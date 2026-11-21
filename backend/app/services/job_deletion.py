"""Delete jobs: refuse running or protected jobs, then remove only the job's own directory."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.jobs.deletion import (
    JobDeletionError,
    move_to_trash,
    purge_deletion_leftovers,
    remove_trash,
    resolve_job_directory,
    validate_job_id,
)
from app.jobs.job_logs import get_job_log_store
from app.jobs.repository import JOB_ID_PATTERN, JobRepository, record_job_number
from app.pipeline.pipeline_manager import PipelineManager

logger = get_logger(__name__)

MAX_BULK_DELETE = 100


@dataclass(frozen=True)
class DeletionOutcome:
    job_id: str
    status: str  # deleted | not_found | refused | failed
    detail: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {"job_id": self.job_id, "status": self.status, "detail": self.detail}


class JobDeletionService:
    """Deletes job workspaces one at a time, holding the job's pipeline lock while doing so."""

    def __init__(self, repository: JobRepository | None = None) -> None:
        self._repository = repository or JobRepository()

    @property
    def repository(self) -> JobRepository:
        return self._repository

    async def delete(self, job_id: str) -> None:
        """Delete one job. Raises ``JobDeletionError`` with a code on refusal or failure."""
        validate_job_id(job_id)
        settings = self._repository.settings
        if job_id in settings.protected_job_id_set:
            raise JobDeletionError(
                "protected", f"{job_id} is protected (PROTECTED_JOB_IDS) and cannot be deleted."
            )

        lock = PipelineManager.job_lock(job_id)
        if lock.locked():
            raise JobDeletionError(
                "running",
                f"{job_id} is running. Cancel the run and wait for it to stop before deleting.",
            )

        jobs_root = self._repository.jobs_root
        async with lock:
            job_directory = resolve_job_directory(jobs_root, job_id)
            # A directory without metadata.json is not a job the API knows about; leave it.
            if job_directory is None or self._repository.get(job_id) is None:
                raise JobDeletionError("not_found", f"Job not found: {job_id}")
            match = JOB_ID_PATTERN.fullmatch(job_id)
            if match:
                record_job_number(jobs_root.resolve(), int(match.group(1)))
            try:
                trash = move_to_trash(jobs_root, job_directory, job_id)
            except OSError as exc:
                raise JobDeletionError("failed", f"Could not delete {job_id}: {exc.strerror}") from exc
            get_job_log_store(jobs_root).forget(job_id)
        PipelineManager.forget(job_id)
        remove_trash(jobs_root, trash)
        purge_deletion_leftovers(jobs_root)
        logger.info("Deleted job | job_id=%s", job_id)

    async def delete_many(self, job_ids: list[str]) -> list[DeletionOutcome]:
        """Delete several jobs, continuing past individual refusals. Duplicates are ignored."""
        outcomes: list[DeletionOutcome] = []
        seen: set[str] = set()
        for job_id in job_ids:
            if job_id in seen:
                continue
            seen.add(job_id)
            try:
                await self.delete(job_id)
                outcomes.append(DeletionOutcome(job_id, "deleted"))
            except JobDeletionError as exc:
                status = {
                    "not_found": "not_found",
                    "failed": "failed",
                }.get(exc.code, "refused")
                outcomes.append(DeletionOutcome(job_id, status, str(exc)))
        return outcomes


def get_job_deletion_service() -> JobDeletionService:
    """FastAPI dependency."""
    return JobDeletionService()
