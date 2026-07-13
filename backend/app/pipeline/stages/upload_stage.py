"""Upload stage — wraps the existing upload service."""

from __future__ import annotations

from app.jobs.repository import JobRepository
from app.models.job import Job
from app.pipeline.pipeline_state import PipelineState
from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.services.upload_service import UploadService


class UploadStage(PipelineStage):
    """Validate uploaded imagery and mark the upload stage complete."""

    STAGE_ID = 1
    STAGE_NAME = "Upload"

    def __init__(
        self,
        upload_service: UploadService | None = None,
        pipeline_state: PipelineState | None = None,
        repository: JobRepository | None = None,
    ) -> None:
        self._upload_service = upload_service or UploadService()
        self._pipeline_state = pipeline_state or PipelineState()
        self._repository = repository or JobRepository()

    @property
    def stage_id(self) -> int:
        return self.STAGE_ID

    def name(self) -> str:
        return self.STAGE_NAME

    def status(self, job: Job) -> str:
        return self._pipeline_state.stage_status(job.id, self.stage_id)

    async def run(self, job: Job, ctx: StageContext) -> StageResult:
        ctx.check_control()

        if job.image_count <= 0:
            previews = self._upload_service.list_previews(self._repository.jobs_root, job.id)
            if not previews:
                ctx.log("No uploaded images found for this job.", level="error")
                return StageResult(
                    success=False,
                    message="Upload images before running the pipeline.",
                )

        ctx.log("Verifying uploaded images...")
        ctx.update_progress(50)
        ctx.check_control()

        completed_at = job.uploaded_at
        self._pipeline_state.mark_upload_complete(job.id, completed_at=completed_at)
        ctx.update_progress(100)
        ctx.log("Upload stage complete.")

        return StageResult(
            success=True,
            message="Upload complete.",
            data={"image_count": job.image_count},
        )

    async def rollback(self, job: Job, ctx: StageContext) -> StageResult:
        self._pipeline_state.mark_stage_waiting(job.id, self.stage_id)
        ctx.log("Upload stage rolled back to waiting.")
        return StageResult(success=True, message="Upload stage reset.")
