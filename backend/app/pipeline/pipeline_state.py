"""Pipeline persistence helpers for ``pipeline.json``."""

from __future__ import annotations

from typing import Any, Literal

from app.core.text import strip_ansi
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
        clear_last_error: bool = False,
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
        if clear_last_error:
            execution["last_error"] = None
        elif last_error is not None:
            execution["last_error"] = last_error
        return self.save(job_id, document)

    def reset_stages_from(self, job_id: str, stage_id: int) -> dict[str, Any]:
        """Return ``stage_id`` and every later stage to ``waiting`` for a rerun.

        Earlier stages and on-disk artifacts are left untouched. Reset stages are tagged
        with ``reset_at`` so ``reconcile_with_job`` does not mark them completed again
        from artifacts left over by the previous run.
        """
        document = self.load(job_id)
        reset_at = utc_now_iso()
        for stage in document["stages"]:
            if stage["id"] < stage_id:
                continue
            stage["status"] = "waiting"
            stage["progress"] = 0
            stage["completed_at"] = None
            stage["reset_at"] = reset_at

        execution = document["execution"]
        execution["status"] = "idle"
        execution["current_stage_id"] = None
        execution["paused_at"] = None
        execution["cancelled_at"] = None
        execution["last_error"] = None
        return self.save(job_id, document)

    def mark_stage_before(self, job_id: str, stage_id: int) -> dict[str, Any]:
        """Persist state immediately before a stage begins."""
        return self.update_stage(
            job_id,
            stage_id,
            status="running",
            progress=0,
            completed_at=None,
            started_at=utc_now_iso(),
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
        document["execution"]["last_error"] = strip_ansi(message)
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
        started_at: str | None = None,
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
            if started_at is not None:
                stage["started_at"] = started_at
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
        changed = False

        if image_count > 0:
            for stage in document["stages"]:
                if stage["id"] != 1:
                    continue
                if stage["status"] == "waiting" and "reset_at" not in stage:
                    stage["status"] = "completed"
                    changed = True
                    stage["progress"] = 100
                    stage["completed_at"] = uploaded_at or utc_now_iso()
                break

        if masked_image_count > 0:
            for stage in document["stages"]:
                if stage["id"] != 2:
                    continue
                if stage["status"] == "waiting" and "reset_at" not in stage:
                    stage["status"] = "completed"
                    changed = True
                    stage["progress"] = 100
                    stage["completed_at"] = utc_now_iso()
                break

        if has_transforms:
            for stage in document["stages"]:
                if stage["id"] != CAMERA_ESTIMATION_STAGE_ID:
                    continue
                if stage["status"] == "waiting" and "reset_at" not in stage:
                    stage["status"] = "completed"
                    changed = True
                    stage["progress"] = 100
                    stage["completed_at"] = camera_estimated_at or utc_now_iso()
                break

        if has_snapshot:
            for stage in document["stages"]:
                if stage["id"] != TRAINING_STAGE_ID:
                    continue
                if stage["status"] == "waiting" and "reset_at" not in stage:
                    stage["status"] = "completed"
                    changed = True
                    stage["progress"] = 100
                    stage["completed_at"] = reconstruction_completed_at or utc_now_iso()
                break

        # Only write when artifacts changed something, so polling GET /pipeline stays read-only
        # and cannot overwrite progress persisted concurrently by a running stage.
        if not changed:
            return document
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

        was_running = execution["status"] == "running"
        execution["status"] = "idle"
        execution["current_stage_id"] = None
        execution["paused_at"] = None
        # A paused run was stopped on purpose; only an interrupted run records an error.
        execution["last_error"] = "Recovered after restart" if was_running else None
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
