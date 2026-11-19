"""Mesh cleanup stage — wraps MeshCleanupEngine via the service layer."""

from __future__ import annotations

from app.models.job import Job
from app.pipeline.pipeline_state import PipelineState
from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.services.mesh_cleanup_service import MeshCleanupError, MeshCleanupService


class MeshCleanupStage(PipelineStage):
    """Validate, repair, smooth and decimate the Stage 5 mesh into separate cleaned outputs."""

    STAGE_ID = 6
    STAGE_NAME = "Mesh Cleanup"

    def __init__(
        self,
        service: MeshCleanupService | None = None,
        pipeline_state: PipelineState | None = None,
    ) -> None:
        self._service = service or MeshCleanupService()
        self._pipeline_state = pipeline_state or PipelineState()

    @property
    def stage_id(self) -> int:
        return self.STAGE_ID

    def name(self) -> str:
        return self.STAGE_NAME

    def status(self, job: Job) -> str:
        return self._pipeline_state.stage_status(job.id, self.stage_id)

    async def run(self, job: Job, ctx: StageContext) -> StageResult:
        ctx.check_control()
        ctx.log("Starting mesh cleanup...")

        validation = self._service.validate(job.id)
        if not validation.success:
            ctx.log(validation.message, level="error")
            return StageResult(
                success=False,
                message=validation.message,
                data={"error_code": validation.error_code},
            )

        try:
            result = await self._service.clean(
                job.id,
                log=ctx.log,
                on_progress=ctx.update_progress,
                check_control=ctx.check_control,
            )
        except MeshCleanupError as exc:
            return StageResult(success=False, message=str(exc))

        return StageResult(success=True, message="Mesh cleanup complete.", data=result)

    async def rollback(self, job: Job, ctx: StageContext) -> StageResult:
        self._pipeline_state.mark_stage_waiting(job.id, self.stage_id)
        ctx.log("Mesh cleanup stage rolled back to waiting (cleaned files are kept).")
        return StageResult(success=True, message="Mesh cleanup stage reset.")
