"""Engine management endpoints (not implemented)."""

from fastapi import APIRouter

router = APIRouter(prefix="/engines", tags=["engines"])

# Future: list engines, engine status, engine configuration
