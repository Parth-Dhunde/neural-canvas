"""Pydantic schemas for pipeline API responses."""

from pydantic import BaseModel, Field


class PipelineStageResponse(BaseModel):
    """Single pipeline stage persisted in ``pipeline.json``."""

    id: int
    name: str
    status: str
    progress: int
    completed_at: str | None = None


class PipelineResponse(BaseModel):
    """Pipeline state returned by the API."""

    stages: list[PipelineStageResponse] = Field(default_factory=list)


class PipelineStartResponse(BaseModel):
    """Response body for pipeline execution endpoints."""

    job_id: str
    stages_run: list[int] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    stopped_reason: str
    processed: int | None = None
    failed: int | None = None
    total: int | None = None
