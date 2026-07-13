"""Pipeline persistence helpers for ``pipeline.json``."""

from __future__ import annotations

from typing import Any, Literal

from app.jobs.pipeline_repository import PipelineRepository
from app.models.job import utc_now_iso
from app.pipeline.constants import CAMERA_ESTIMATION_STAGE_ID, PIPELINE_STAGE_DEFINITIONS, TRAINING_STAGE_ID

ExecutionStatus = Literal["idle", "running", "paused", "cancelled"]

DEFAULT_EXECUTION: dict[str, Any] = {
    "status": "idle",
    "current_stage_id": None,
    "paused_at": None,
    "cancelled_at": None,
    "last_error": None,
}


class PipelineState:
    """Read and write pipeline documents, including execution metadata."""

    def __init__(self, repository: PipelineRepository | None = None) -> None:
        self._repository = repository or PipelineRepository()

    @property
    def repository(self) -> PipelineRepository:
        return self._repository

    def load(self, job_id: str) -> dict[str, Any]:
        document = self._repository.load_or_create(job_id)
        document = self._ensure_execution(document)
        return self._normalize_stages(job_id, document)

    def _normalize_stages(self, job_id: str, document: dict[str, Any]) -> dict[str, Any]:
        existing_by_id = {
            stage["id"]: stage for stage in document.get("stages", []) if "id" in stage
        }
        normalized: list[dict[str, Any]] = []
        changed = len(existing_by_id) != len(PIPELINE_STAGE_DEFINITIONS)

        for stage_id, stage_name in PIPELINE_STAGE_DEFINITIONS:
            if stage_id in existing_by_id:
                stage = dict(existing_by_id[stage_id])
                if stage.get("name") != stage_name:
                    stage["name"] = stage_name
                    changed = True
            else:
                stage = {
                    "id": stage_id,
                    "name": stage_name,
                    "status": "waiting",
                    "progress": 0,
                    "completed_at": None,
                }
                changed = True
            normalized.append(stage)

        document["stages"] = normalized
        if changed:
            return self._repository.save(job_id, document)
        return document

    def save(self, job_id: str, document: dict[str, Any]) -> dict[str, Any]:
        return self._repository.save(job_id, self._ensure_execution(document))

    def get_stage(self, job_id: str, stage_id: int) -> dict[str, Any] | None:
        document = self.load(job_id)
        for stage in document["stages"]:
            if stage["id"] == stage_id:
                return stage
        return None

    def stage_status(self, job_id: str, stage_id: int) -> str:
        stage = self.get_stage(job_id, stage_id)
        return str(stage["status"]) if stage is not None else "waiting"

    def execution_status(self, job_id: str) -> ExecutionStatus:
        document = self.load(job_id)
        return document["execution"]["status"]

    def set_execution(
        self,
        job_id: str,
        *,
        status: ExecutionStatus | None = None,
        current_stage_id: int | None = None,
        clear_current_stage: bool = False,
        paused_at: str | None = None,
        cancelled_at: str | None = None,
        last_error: str | None = None,
    ) -> dict[str, Any]:
        document = self.load(job_id)
        execution = document["execution"]
        if status is not None:
            execution["status"] = status
        if clear_current_stage:
            execution["current_stage_id"] = None
        elif current_stage_id is not None:
            execution["current_stage_id"] = current_stage_id
        if paused_at is not None:
            execution["paused_at"] = paused_at
        if cancelled_at is not None:
            execution["cancelled_at"] = cancelled_at
        if last_error is not None:
            execution["last_error"] = last_error
        return self.save(job_id, document)

    def mark_stage_before(self, job_id: str, stage_id: int) -> dict[str, Any]:
        """Persist state immediately before a stage begins."""
        return self.update_stage(
            job_id,
            stage_id,
            status="running",
            progress=0,
            completed_at=None,
        )

    def mark_stage_running(self, job_id: str, stage_id: int, *, progress: int) -> dict[str, Any]:
        """Persist in-flight stage progress."""
        return self.update_stage(job_id, stage_id, status="running", progress=progress)

    def mark_stage_completed(self, job_id: str, stage_id: int) -> dict[str, Any]:
        """Persist successful stage completion."""
        return self.update_stage(
            job_id,
            stage_id,
            status="completed",
            progress=100,
            completed_at=utc_now_iso(),
        )

    def mark_stage_failed(self, job_id: str, stage_id: int, *, message: str) -> dict[str, Any]:
        document = self.load(job_id)
        for stage in document["stages"]:
            if stage["id"] != stage_id:
                continue
            stage["status"] = "failed"
            break
        document["execution"]["last_error"] = message
        return self.save(job_id, document)

    def mark_stage_waiting(self, job_id: str, stage_id: int) -> dict[str, Any]:
        return self.update_stage(
            job_id,
            stage_id,
            status="waiting",
            progress=0,
            completed_at=None,
        )

    def update_stage(
        self,
        job_id: str,
        stage_id: int,
        *,
        status: str | None = None,
        progress: int | None = None,
        completed_at: str | None = None,
    ) -> dict[str, Any]:
        document = self.load(job_id)
        for stage in document["stages"]:
            if stage["id"] != stage_id:
                continue
            if status is not None:
                stage["status"] = status
            if progress is not None:
                stage["progress"] = progress
            if completed_at is not None:
                stage["completed_at"] = completed_at
            break
        return self.save(job_id, document)

    def mark_upload_complete(self, job_id: str, *, completed_at: str | None = None) -> dict[str, Any]:
        return self.update_stage(
            job_id,
            1,
            status="completed",
            progress=100,
            completed_at=completed_at or utc_now_iso(),
        )

    def reconcile_with_job(
        self,
        job_id: str,
        *,
        image_count: int,
        uploaded_at: str | None,
        masked_image_count: int,
        has_transforms: bool = False,
        camera_estimated_at: str | None = None,
        has_snapshot: bool = False,
        reconstruction_completed_at: str | None = None,
    ) -> dict[str, Any]:
        document = self.load(job_id)

        if image_count > 0:
            for stage in document["stages"]:
                if stage["id"] != 1:
                    continue
                if stage["status"] == "waiting":
                    stage["status"] = "completed"
                    stage["progress"] = 100
                    stage["completed_at"] = uploaded_at or utc_now_iso()
                break

        if masked_image_count > 0:
            for stage in document["stages"]:
                if stage["id"] != 2:
                    continue
                if stage["status"] == "waiting":
                    stage["status"] = "completed"
                    stage["progress"] = 100
                    stage["completed_at"] = utc_now_iso()
                break

        if has_transforms:
            for stage in document["stages"]:
                if stage["id"] != CAMERA_ESTIMATION_STAGE_ID:
                    continue
                if stage["status"] == "waiting":
                    stage["status"] = "completed"
                    stage["progress"] = 100
                    stage["completed_at"] = camera_estimated_at or utc_now_iso()
                break

        if has_snapshot:
            for stage in document["stages"]:
                if stage["id"] != TRAINING_STAGE_ID:
                    continue
                if stage["status"] == "waiting":
                    stage["status"] = "completed"
                    stage["progress"] = 100
                    stage["completed_at"] = reconstruction_completed_at or utc_now_iso()
                break

        return self.save(job_id, document)

    def recover_after_restart(self, job_id: str) -> dict[str, Any]:
        """Reset interrupted execution state after a process restart."""
        document = self.load(job_id)
        execution = document["execution"]
        if execution["status"] not in {"running", "paused"}:
            return document

        interrupted_stage_id = execution.get("current_stage_id")
        if isinstance(interrupted_stage_id, int):
            for stage in document["stages"]:
                if stage["id"] != interrupted_stage_id:
                    continue
                if stage["status"] == "running":
                    stage["status"] = "waiting"
                    stage["progress"] = 0
                    stage["completed_at"] = None
                break

        execution["status"] = "idle"
        execution["current_stage_id"] = None
        execution["paused_at"] = None
        execution["last_error"] = "Recovered after restart"
        return self.save(job_id, document)

    @staticmethod
    def _ensure_execution(document: dict[str, Any]) -> dict[str, Any]:
        execution = document.get("execution")
        if not isinstance(execution, dict):
            document["execution"] = dict(DEFAULT_EXECUTION)
            return document

        merged = dict(DEFAULT_EXECUTION)
        merged.update(execution)
        document["execution"] = merged
        return document
