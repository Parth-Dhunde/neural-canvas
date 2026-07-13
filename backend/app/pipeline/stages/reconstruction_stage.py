"""Reconstruction stage — wraps ReconstructionEngine via the service layer."""

from __future__ import annotations

from app.models.job import Job
from app.pipeline.pipeline_state import PipelineState
from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.services.reconstruction_service import ReconstructionError, ReconstructionService


class ReconstructionStage(PipelineStage):
    """Run neural reconstruction for a job."""

    STAGE_ID = 4
    STAGE_NAME = "Reconstruction"

    def __init__(
        self,
        service: ReconstructionService | None = None,
        pipeline_state: PipelineState | None = None,
    ) -> None:
        self._service = service or ReconstructionService()
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
        ctx.log("Starting reconstruction...")

        validation = self._service.validate(job.id)
        if not validation.success:
            ctx.log(validation.message, level="error")
            return StageResult(success=False, message=validation.message)

        try:
            result = await self._service.run_reconstruction(
                job.id,
                log=ctx.log,
                on_progress=ctx.update_progress,
                check_control=ctx.check_control,
            )
        except ReconstructionError as exc:
            ctx.log(str(exc), level="error")
            return StageResult(success=False, message=str(exc))

        ctx.log("Training completed.")
        return StageResult(
            success=True,
            message="Reconstruction complete.",
            data=result,
        )

    async def rollback(self, job: Job, ctx: StageContext) -> StageResult:
        self._pipeline_state.mark_stage_waiting(job.id, self.stage_id)
        ctx.log("Reconstruction stage rolled back to waiting.")
        return StageResult(success=True, message="Reconstruction stage reset.")
