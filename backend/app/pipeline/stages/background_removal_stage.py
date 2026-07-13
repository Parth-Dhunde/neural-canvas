"""Background removal stage — wraps BackgroundRemovalEngine via the service layer."""

from __future__ import annotations

from app.models.job import Job
from app.pipeline.pipeline_state import PipelineState
from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.services.background_removal_service import BackgroundRemovalService


class BackgroundRemovalStage(PipelineStage):
    """Run background removal for all uploaded source images."""

    STAGE_ID = 2
    STAGE_NAME = "Background Removal"

    def __init__(
        self,
        service: BackgroundRemovalService | None = None,
        pipeline_state: PipelineState | None = None,
    ) -> None:
        self._service = service or BackgroundRemovalService()
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
        ctx.log("Starting background removal...")

        try:
            result = await self._service.process_images(
                job.id,
                log=ctx.log,
                on_progress=ctx.update_progress,
                check_control=ctx.check_control,
            )
        except Exception as exc:
            ctx.log(f"Background removal failed: {exc}", level="error")
            return StageResult(success=False, message=str(exc))

        if result["failed"] > 0:
            ctx.log(
                f"Background removal completed with {result['failed']} failure(s).",
                level="warn",
            )

        ctx.log("Finished background removal.")
        return StageResult(
            success=True,
            message="Background removal complete.",
            data=result,
        )

    async def rollback(self, job: Job, ctx: StageContext) -> StageResult:
        self._pipeline_state.mark_stage_waiting(job.id, self.stage_id)
        ctx.log("Background removal stage rolled back to waiting.")
        return StageResult(success=True, message="Background removal stage reset.")
