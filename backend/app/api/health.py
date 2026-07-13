"""Health check endpoints.

Routes are mounted at the application root in ``app.main`` (``GET /health``).
This module is kept for future ``/api`` prefix migration.
"""

from fastapi import APIRouter

from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Verify that the backend is running."""
    return HealthResponse(status="ok")
