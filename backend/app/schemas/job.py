"""Pydantic schemas for job API requests and responses."""

from typing import Any

from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    """Request body for ``POST /api/jobs``."""

    name: str | None = Field(
        default=None,
        description="Human-readable job name. Defaults to the job identifier.",
    )
    engine: str = Field(
        description='Reconstruction engine identifier, e.g. "Instant-NGP".',
    )


class JobStageSummary(BaseModel):
    """One pipeline stage as recorded in ``pipeline.json``."""

    id: int
    name: str
    status: str
    progress: int
    started_at: str | None = None
    completed_at: str | None = None


class JobOutputsSummary(BaseModel):
    """Which outputs exist for a job (Stage 5 mesh, Stage 6 cleanup, Stage 7 exports)."""

    mesh: bool = False
    cleaned_mesh: bool = False
    exports: dict[str, list[str]] = Field(default_factory=dict)


class JobResponse(BaseModel):
    """Single job returned by the API.

    ``status`` and ``progress`` are derived from the persisted pipeline stages, so they stay
    correct for jobs whose stored job-level fields predate lifecycle tracking.
    """

    id: str
    name: str
    engine: str
    job_type: str = "image_to_3d"
    status: str
    progress: int
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    interrupted: bool = False
    failed_stage: dict[str, Any] | None = None
    last_error: str | None = None
    stages: list[JobStageSummary] = Field(default_factory=list)
    training_duration_seconds: float | None = None
    pipeline_duration_seconds: float | None = None
    training_metrics: dict[str, Any] | None = None
    psnr_db: float | None = None
    outputs: JobOutputsSummary = Field(default_factory=JobOutputsSummary)
    image_count: int = 0
    uploaded_at: str | None = None
    image_filenames: list[str] = Field(default_factory=list)
    camera_estimated_at: str | None = None
    transforms_path: str | None = None
    registered_image_count: int = 0
    reconstruction_started_at: str | None = None
    reconstruction_completed_at: str | None = None
    snapshot_path: str | None = None
    mesh_generated_at: str | None = None
    mesh_path: str | None = None
    mesh_formats: list[str] = Field(default_factory=list)
    vertex_count: int = 0
    triangle_count: int = 0
    mesh_cleanup: dict[str, Any] | None = None
    exports: dict[str, Any] | None = None


class JobListResponse(BaseModel):
    """Collection of jobs returned by ``GET /api/jobs``."""

    jobs: list[JobResponse]
    total: int


class UploadResponse(BaseModel):
    """Response body for ``POST /api/jobs/{job_id}/upload``."""

    job_id: str
    uploaded: list[str]
    image_count: int
    uploaded_at: str
    previews: list[str]


class BackgroundRemovalResponse(BaseModel):
    """Response body for ``POST /api/jobs/{job_id}/background-removal``."""

    job_id: str
    processed: int
    failed: int
    total: int
    logs: list[str]


class JobBulkDeleteRequest(BaseModel):
    """Request body for ``POST /api/jobs/bulk-delete``."""

    job_ids: list[str] = Field(min_length=1, max_length=100)


class JobDeleteOutcome(BaseModel):
    job_id: str
    status: str = Field(description="deleted, not_found, refused or failed")
    detail: str | None = None


class JobBulkDeleteResponse(BaseModel):
    """Response body for ``POST /api/jobs/bulk-delete``."""

    results: list[JobDeleteOutcome]
    deleted: int
