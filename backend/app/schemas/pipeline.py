"""Pydantic schemas for pipeline API responses."""

from pydantic import BaseModel, Field


class PipelineStageResponse(BaseModel):
    """Single pipeline stage persisted in ``pipeline.json``."""

    id: int
    name: str
    status: str
    progress: int
    completed_at: str | None = None


class PipelineExecutionResponse(BaseModel):
    """Execution metadata persisted in ``pipeline.json``."""

    status: str = "idle"
    current_stage_id: int | None = None
    last_error: str | None = None


class PipelineResponse(BaseModel):
    """Pipeline state returned by the API."""

    stages: list[PipelineStageResponse] = Field(default_factory=list)
    execution: PipelineExecutionResponse | None = None


class JobLogEntryResponse(BaseModel):
    """Single pipeline log entry."""

    seq: int
    time: str
    level: str
    message: str
    stage_id: int | None = None


class JobLogsResponse(BaseModel):
    """Incremental page of pipeline log entries for ``GET /api/jobs/{job_id}/logs``."""

    job_id: str
    entries: list[JobLogEntryResponse] = Field(default_factory=list)
    next_after: int = Field(description="Pass as ``after`` on the next poll.")
    last_seq: int
    has_more: bool = Field(description="More entries are available immediately.")
    truncated: bool = Field(
        description="Older entries were dropped from the in-memory buffer (still on disk)."
    )
    reset: bool = Field(description="The cursor was ahead of the log; reading restarted at 0.")


class PipelineStartResponse(BaseModel):
    """Response body for pipeline execution endpoints."""

    job_id: str
    stages_run: list[int] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    stopped_reason: str
    processed: int | None = None
    failed: int | None = None
    total: int | None = None
