"""Pipeline stage persistence for reconstruction jobs."""

import json
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.jobs.structure import JOB_PIPELINE_FILE, job_root_path
from app.pipeline.constants import (
    BACKGROUND_REMOVAL_STAGE_ID,
    PIPELINE_STAGE_NAMES,
    UPLOAD_STAGE_ID,
)

# Re-export stage identifiers for backwards compatibility.
__all__ = [
    "BACKGROUND_REMOVAL_STAGE_ID",
    "PIPELINE_STAGE_NAMES",
    "PipelineRepository",
    "UPLOAD_STAGE_ID",
]

class PipelineRepository:
    """Read and write per-job pipeline state to ``pipeline.json``."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def jobs_root(self) -> Path:
        return self._settings.jobs_path

    def pipeline_path(self, job_id: str) -> Path:
        return job_root_path(self.jobs_root, job_id) / JOB_PIPELINE_FILE

    def create_initial(self, job_id: str) -> dict[str, Any]:
        """Create the default pipeline document for a new job."""
        from app.pipeline.pipeline_manager import PipelineManager

        return PipelineManager().initialize(job_id)

    def load(self, job_id: str) -> dict[str, Any] | None:
        """Load pipeline state from disk."""
        path = self.pipeline_path(job_id)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def load_or_create(self, job_id: str) -> dict[str, Any]:
        """Return existing pipeline state or initialize a new document."""
        existing = self.load(job_id)
        if existing is not None:
            return existing
        return self.create_initial(job_id)

    def save(self, job_id: str, document: dict[str, Any]) -> dict[str, Any]:
        """Persist pipeline state to disk."""
        path = self.pipeline_path(job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        return document

    def get_stage(self, job_id: str, stage_id: int) -> dict[str, Any] | None:
        document = self.load_or_create(job_id)
        for stage in document["stages"]:
            if stage["id"] == stage_id:
                return stage
        return None

    def update_stage(
        self,
        job_id: str,
        stage_id: int,
        *,
        status: str | None = None,
        progress: int | None = None,
        completed_at: str | None = None,
    ) -> dict[str, Any]:
        """Update a single stage inside the pipeline document."""
        document = self.load_or_create(job_id)
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

    def mark_upload_complete(self, job_id: str) -> dict[str, Any]:
        """Mark stage 1 as completed after a successful upload."""
        from app.models.job import utc_now_iso

        return self.update_stage(
            job_id,
            UPLOAD_STAGE_ID,
            status="completed",
            progress=100,
            completed_at=utc_now_iso(),
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
        """Align persisted pipeline stages with on-disk job artifacts."""
        from app.pipeline.pipeline_state import PipelineState

        return PipelineState(self).reconcile_with_job(
            job_id,
            image_count=image_count,
            uploaded_at=uploaded_at,
            masked_image_count=masked_image_count,
            has_transforms=has_transforms,
            camera_estimated_at=camera_estimated_at,
            has_snapshot=has_snapshot,
            reconstruction_completed_at=reconstruction_completed_at,
        )
