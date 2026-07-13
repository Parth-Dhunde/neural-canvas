"""Pydantic schemas for job API requests and responses."""

from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    """Request body for ``POST /api/jobs``."""

    name: str | None = Field(
        default=None,
        description="Human-readable job name. Defaults to the job identifier.",
    )
    engine: str = Field(
        description='Reconstruction engine identifier, e.g. "Instant-NGP" or "Custom NeRF".',
    )


class JobResponse(BaseModel):
    """Single job returned by the API."""

    id: str
    name: str
    engine: str
    status: str
    progress: int
    created_at: str
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
