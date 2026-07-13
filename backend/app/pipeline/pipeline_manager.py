"""Central orchestrator for reconstruction pipeline execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.jobs.repository import JobRepository
from app.models.job import Job, utc_now_iso
from app.pipeline.pipeline_state import PipelineState
from app.pipeline.stage import PipelineStage, StageResult
from app.pipeline.stage_registry import StageRegistry

logger = get_logger(__name__)


class PipelineControlError(Exception):
    """Raised when pipeline execution is interrupted by pause or cancel."""


class PipelineNotFoundError(Exception):
    """Raised when a job does not exist."""


class PipelineBusyError(Exception):
    """Raised when a job pipeline is already running."""


@dataclass
class _JobRunControl:
    paused: bool = False
    cancelled: bool = False


@dataclass
class _StageContext:
    manager: "PipelineManager"
    job_id: str
    stage_id: int

    def log(self, message: str, level: str = "info") -> None:
        self.manager.log(self.job_id, message, level=level)

    def update_progress(self, progress: int) -> None:
        self.manager._state.mark_stage_running(self.job_id, self.stage_id, progress=progress)

    def check_control(self) -> None:
        self.manager._check_control(self.job_id)


@dataclass
class PipelineRunResult:
    """Summary returned after pipeline execution."""

    job_id: str
    stages_run: list[int] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    stopped_reason: str = "completed"
    last_result: StageResult | None = None


class PipelineManager:
    """Owns pipeline execution, logging, and persistence."""

    def __init__(
        self,
        registry: StageRegistry | None = None,
        state: PipelineState | None = None,
        repository: JobRepository | None = None,
    ) -> None:
        self._registry = registry or StageRegistry()
        self._state = state or PipelineState()
        self._repository = repository or JobRepository()
        self._controls: dict[str, _JobRunControl] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._job_logs: dict[str, list[str]] = {}

    def initialize(self, job_id: str) -> dict[str, Any]:
        """Create the initial ``pipeline.json`` for a new job."""
        document = {
            "execution": {
                "status": "idle",
                "current_stage_id": None,
                "paused_at": None,
                "cancelled_at": None,
                "last_error": None,
            },
            "stages": self._registry.create_initial_stages(),
        }
        return self._state.save(job_id, document)

    def log(self, job_id: str, message: str, *, level: str = "info") -> None:
        """Record a pipeline log line and emit it to the application logger."""
        line = f"[{job_id}] {message}"
        self._job_logs.setdefault(job_id, []).append(line)
        log_fn = getattr(logger, "warning" if level == "warn" else level, logger.info)
        log_fn(line)

    def get_logs(self, job_id: str) -> list[str]:
        return list(self._job_logs.get(job_id, []))

    def clear_logs(self, job_id: str) -> None:
        self._job_logs[job_id] = []

    def get_pipeline_document(self, job_id: str) -> dict[str, Any]:
        return self._state.load(job_id)

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
        return self._state.reconcile_with_job(
            job_id,
            image_count=image_count,
            uploaded_at=uploaded_at,
            masked_image_count=masked_image_count,
            has_transforms=has_transforms,
            camera_estimated_at=camera_estimated_at,
            has_snapshot=has_snapshot,
            reconstruction_completed_at=reconstruction_completed_at,
        )

    async def on_upload_complete(self, job_id: str, *, completed_at: str | None = None) -> None:
        """Mark the upload stage complete after files are saved."""
        self._state.mark_upload_complete(job_id, completed_at=completed_at)
        self.log(job_id, "Upload saved and stage marked complete.")

    async def run_next_stage(self, job_id: str) -> PipelineRunResult:
        """Execute the next incomplete stage for a job."""
        job = self._require_job(job_id)
        next_stage = self._next_runnable_stage(job_id)
        if next_stage is None:
            return PipelineRunResult(
                job_id=job_id,
                logs=self.get_logs(job_id),
                stopped_reason="no_pending_stage",
            )
        return await self._run_single_stage(job, next_stage)

    async def run_stage(self, job_id: str, stage_id: int) -> PipelineRunResult:
        """Execute a specific stage by identifier."""
        job = self._require_job(job_id)
        stage = self._registry.get(stage_id)
        if stage is None:
            raise ValueError(f"Unknown stage id: {stage_id}")
        return await self._run_single_stage(job, stage)

    async def run_pipeline(self, job_id: str) -> PipelineRunResult:
        """Run implemented stages sequentially until completion or a blocker."""
        job = self._require_job(job_id)
        result = PipelineRunResult(job_id=job_id)

        async with self._job_lock(job_id):
            self._ensure_recovered(job_id)
            self._set_running(job_id)
            self.clear_logs(job_id)
            self.log(job_id, "Pipeline started.")

            try:
                for stage in self._registry.all():
                    if not stage.is_implemented:
                        placeholder = await self._execute_stage(job, stage)
                        result.last_result = placeholder
                        result.stopped_reason = "not_implemented"
                        break

                    if self._is_stage_complete(job_id, stage.stage_id):
                        continue

                    stage_result = await self._execute_stage(job, stage)
                    result.stages_run.append(stage.stage_id)
                    result.last_result = stage_result

                    if not stage_result.success:
                        result.stopped_reason = "stage_failed"
                        break
                else:
                    result.stopped_reason = "completed"
            except PipelineControlError as exc:
                result.stopped_reason = str(exc)
            finally:
                self._finish_execution(job_id)
                result.logs = self.get_logs(job_id)

        return result

    def pause(self, job_id: str) -> dict[str, Any]:
        """Pause an in-flight pipeline."""
        control = self._controls.setdefault(job_id, _JobRunControl())
        control.paused = True
        document = self._state.set_execution(
            job_id,
            status="paused",
            paused_at=utc_now_iso(),
        )
        self.log(job_id, "Pipeline paused.")
        return document

    def resume(self, job_id: str) -> dict[str, Any]:
        """Resume a paused pipeline."""
        control = self._controls.setdefault(job_id, _JobRunControl())
        control.paused = False
        document = self._state.set_execution(job_id, status="running", paused_at=None)
        self.log(job_id, "Pipeline resumed.")
        return document

    def cancel(self, job_id: str) -> dict[str, Any]:
        """Cancel an in-flight pipeline."""
        control = self._controls.setdefault(job_id, _JobRunControl())
        control.cancelled = True
        control.paused = False
        document = self._state.set_execution(
            job_id,
            status="cancelled",
            clear_current_stage=True,
            cancelled_at=utc_now_iso(),
        )
        self.log(job_id, "Pipeline cancelled.")
        return document

    def recover(self, job_id: str) -> dict[str, Any]:
        """Recover pipeline state after a process restart."""
        self._controls.pop(job_id, None)
        document = self._state.recover_after_restart(job_id)
        self.log(job_id, "Pipeline state recovered after restart.")
        return document

    def _require_job(self, job_id: str) -> Job:
        job = self._repository.get(job_id)
        if job is None:
            raise PipelineNotFoundError(f"Job not found: {job_id}")
        return job

    def _job_lock(self, job_id: str) -> asyncio.Lock:
        if job_id not in self._locks:
            self._locks[job_id] = asyncio.Lock()
        return self._locks[job_id]

    def _ensure_recovered(self, job_id: str) -> None:
        status = self._state.execution_status(job_id)
        if status in {"running", "paused"}:
            self.recover(job_id)

    def _set_running(self, job_id: str) -> None:
        self._controls[job_id] = _JobRunControl()
        self._state.set_execution(job_id, status="running", last_error=None)

    def _finish_execution(self, job_id: str) -> None:
        control = self._controls.get(job_id)
        if control and control.cancelled:
            status = "cancelled"
        elif control and control.paused:
            status = "paused"
        else:
            status = "idle"
        self._state.set_execution(job_id, status=status, clear_current_stage=True)
        self._controls.pop(job_id, None)

    def _check_control(self, job_id: str) -> None:
        control = self._controls.get(job_id)
        if control is None:
            return
        if control.cancelled:
            raise PipelineControlError("cancelled")
        if control.paused:
            raise PipelineControlError("paused")

    def _is_stage_complete(self, job_id: str, stage_id: int) -> bool:
        stage = self._state.get_stage(job_id, stage_id)
        return stage is not None and stage.get("status") == "completed"

    def _next_runnable_stage(self, job_id: str) -> PipelineStage | None:
        for stage in self._registry.all():
            if self._is_stage_complete(job_id, stage.stage_id):
                continue
            return stage
        return None

    async def _run_single_stage(self, job: Job, stage: PipelineStage) -> PipelineRunResult:
        result = PipelineRunResult(job_id=job.id)

        async with self._job_lock(job.id):
            self._ensure_recovered(job.id)
            self._set_running(job.id)
            self.log(job.id, f"Running stage {stage.stage_id}: {stage.name()}")

            try:
                stage_result = await self._execute_stage(job, stage)
                result.stages_run.append(stage.stage_id)
                result.last_result = stage_result
                result.stopped_reason = "completed" if stage_result.success else "stage_failed"
            except PipelineControlError as exc:
                result.stopped_reason = str(exc)
            finally:
                self._finish_execution(job.id)
                result.logs = self.get_logs(job.id)

        return result

    async def _execute_stage(self, job: Job, stage: PipelineStage) -> StageResult:
        ctx = _StageContext(manager=self, job_id=job.id, stage_id=stage.stage_id)

        if not stage.is_implemented:
            return await stage.run(job, ctx)

        self._state.mark_stage_before(job.id, stage.stage_id)
        self._state.set_execution(job.id, current_stage_id=stage.stage_id)
        self.log(job.id, f"Stage {stage.stage_id} ({stage.name()}) starting.")

        try:
            stage_result = await stage.run(job, ctx)
        except PipelineControlError:
            raise
        except Exception as exc:
            self._state.mark_stage_failed(job.id, stage.stage_id, message=str(exc))
            self.log(job.id, f"Stage {stage.stage_id} failed: {exc}", level="error")
            return StageResult(success=False, message=str(exc))

        if stage_result.implemented and stage_result.success:
            self._state.mark_stage_completed(job.id, stage.stage_id)
            self.log(job.id, f"Stage {stage.stage_id} ({stage.name()}) completed.")
        elif stage_result.implemented and not stage_result.success:
            self._state.mark_stage_failed(job.id, stage.stage_id, message=stage_result.message)
            self.log(job.id, f"Stage {stage.stage_id} failed: {stage_result.message}", level="error")

        return stage_result


def get_pipeline_manager() -> PipelineManager:
    """FastAPI dependency that returns a pipeline manager instance."""
    return PipelineManager()
