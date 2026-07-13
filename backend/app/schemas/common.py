"""Health and version response schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response body for ``GET /health``."""

    status: str


class VersionResponse(BaseModel):
    """Response body for ``GET /version``."""

    version: str
    app: str


class RootResponse(BaseModel):
    """Response body for ``GET /``."""

    app: str
    status: str
    docs: str
