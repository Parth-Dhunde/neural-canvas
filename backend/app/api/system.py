"""System status API routes."""

from fastapi import APIRouter

from app.services.system_status import get_last_validation, run_startup_validation

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/engines")
async def get_engine_status() -> dict[str, object]:
    """Return installation and readiness status for reconstruction engines."""
    result = get_last_validation() or run_startup_validation()
    return result.to_api_dict()
