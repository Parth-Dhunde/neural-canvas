"""Export stage — verifies mesh files on disk and publishes the download manifest."""

from __future__ import annotations

from app.jobs.repository import JobRepository
from app.jobs.structure import EXPORT_MANIFEST_FILE, EXPORTS_DIR
from app.models.job import Job
from app.pipeline.pipeline_state import PipelineState
from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.services.export_service import ExportService, cleanup_is_current


class ExportStage(PipelineStage):
    """Check that exported meshes really exist and are readable, then write the manifest."""

    STAGE_ID = 7
    STAGE_NAME = "Export"

    def __init__(
        self,
        service: ExportService | None = None,
        repository: JobRepository | None = None,
        pipeline_state: PipelineState | None = None,
    ) -> None:
        self._repository = repository or JobRepository()
        self._service = service or ExportService(self._repository)
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
        ctx.log("Verifying export files...")
        # Re-read: Stage 6 updated metadata after this Job object was loaded.
        job = self._repository.get(job.id) or job
        manifest = self._service.manifest(job)

        for name, variant in manifest["variants"].items():
            for fmt, entry in variant["formats"].items():
                if entry["available"]:
                    ctx.log(f"{name} {fmt.upper()}: {entry['bytes']} bytes -> {entry['url']}")
                else:
                    ctx.log(f"{name} {fmt.upper()}: {entry.get('problem')}", level="warn")

        cleaned = manifest["variants"]["cleaned"]
        if not cleanup_is_current(job):
            message = f"No current cleaned mesh to export ({cleaned['unavailable_reason']})."
            ctx.log(message, level="error")
            return StageResult(success=False, message=message)
        if not cleaned["complete"]:
            missing = [f for f, e in cleaned["formats"].items() if not e["available"]]
            message = f"Cleaned outputs failed verification: {', '.join(missing)}."
            ctx.log(message, level="error")
            return StageResult(success=False, message=message)

        written = self._service.write_manifest(job)
        summary = {
            "generated_at": written["generated_at"],
            "preferred": written["preferred"],
            "manifest_path": f"{EXPORTS_DIR}/{EXPORT_MANIFEST_FILE}",
            "available": {
                name: [fmt for fmt, e in variant["formats"].items() if e["available"]]
                for name, variant in written["variants"].items()
            },
        }
        self._repository.update(job.id, exports=summary)
        ctx.update_progress(100)
        ctx.log(f"Export ready; viewer uses the {written['preferred']} GLB.", level="ok")
        return StageResult(success=True, message="Export complete.", data=summary)

    async def rollback(self, job: Job, ctx: StageContext) -> StageResult:
        self._pipeline_state.mark_stage_waiting(job.id, self.stage_id)
        ctx.log("Export stage rolled back to waiting.")
        return StageResult(success=True, message="Export stage reset.")
