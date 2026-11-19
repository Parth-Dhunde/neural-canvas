"""Hardware metrics endpoints."""

from fastapi import APIRouter

from app.services.hardware_info import collect_hardware_summary

router = APIRouter(prefix="/hardware", tags=["hardware"])


@router.get("")
async def get_hardware() -> dict[str, str]:
    """Return detected host GPU, driver, CUDA, memory, and temperature."""
    return collect_hardware_summary().to_api_dict()
