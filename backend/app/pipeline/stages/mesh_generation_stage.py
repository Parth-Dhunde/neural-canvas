"""Mesh generation stage — wraps MeshGenerationEngine via the service layer."""

from __future__ import annotations

from app.models.job import Job
from app.pipeline.pipeline_state import PipelineState
from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.services.mesh_generation_service import MeshGenerationError, MeshGenerationService


class MeshGenerationStage(PipelineStage):
    """Generate a mesh from reconstruction outputs."""

    STAGE_ID = 5
    STAGE_NAME = "Mesh Generation"

    def __init__(
        self,
        service: MeshGenerationService | None = None,
        pipeline_state: PipelineState | None = None,
    ) -> None:
        self._service = service or MeshGenerationService()
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
        ctx.log("Starting mesh generation...")

        validation = self._service.validate(job.id)
        if not validation.success:
            ctx.log(validation.message, level="error")
            return StageResult(
                success=False,
                message=validation.message,
                data={"error_code": validation.error_code, **validation.data},
            )

        ctx.log("Loading snapshot...")
        ctx.update_progress(10)
        ctx.check_control()

        try:
            result = await self._service.generate_mesh(
                job.id,
                log=ctx.log,
                on_progress=ctx.update_progress,
                check_control=ctx.check_control,
            )
        except MeshGenerationError as exc:
            ctx.log(str(exc), level="error")
            return StageResult(success=False, message=str(exc))

        ctx.log("Mesh generation completed.")
        return StageResult(
            success=True,
            message="Mesh generation complete.",
            data=result,
        )

    async def rollback(self, job: Job, ctx: StageContext) -> StageResult:
        self._pipeline_state.mark_stage_waiting(job.id, self.stage_id)
        ctx.log("Mesh generation stage rolled back to waiting.")
        return StageResult(success=True, message="Mesh generation stage reset.")

