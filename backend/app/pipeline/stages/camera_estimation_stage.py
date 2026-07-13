"""Camera estimation stage — wraps CameraEstimationEngine via the service layer."""

from __future__ import annotations

from app.models.job import Job
from app.pipeline.pipeline_state import PipelineState
from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.services.camera_estimation_service import (
    CameraEstimationError,
    CameraEstimationService,
)


class CameraEstimationStage(PipelineStage):
    """Estimate camera poses from masked images."""

    STAGE_ID = 3
    STAGE_NAME = "Camera Estimation"

    def __init__(
        self,
        service: CameraEstimationService | None = None,
        pipeline_state: PipelineState | None = None,
    ) -> None:
        self._service = service or CameraEstimationService()
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
        ctx.log("Starting camera estimation...")

        validation = self._service.validate(job.id)
        if not validation.success:
            ctx.log(validation.message, level="error")
            return StageResult(success=False, message=validation.message)

        try:
            result = await self._service.estimate_cameras(
                job.id,
                log=ctx.log,
                on_progress=ctx.update_progress,
                check_control=ctx.check_control,
            )
        except CameraEstimationError as exc:
            ctx.log(str(exc), level="error")
            return StageResult(success=False, message=str(exc))

        ctx.log("Camera estimation completed.")
        return StageResult(
            success=True,
            message="Camera estimation complete.",
            data=result,
        )

    async def rollback(self, job: Job, ctx: StageContext) -> StageResult:
        self._pipeline_state.mark_stage_waiting(job.id, self.stage_id)
        ctx.log("Camera estimation stage rolled back to waiting.")
        return StageResult(success=True, message="Camera estimation stage reset.")
