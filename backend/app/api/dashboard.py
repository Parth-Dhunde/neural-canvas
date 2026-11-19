"""Dashboard summary endpoint."""

from fastapi import APIRouter

from app.services.dashboard_stats import build_dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def get_dashboard_summary() -> dict[str, object]:
    """Job counts, training and storage statistics, and per-engine medians.

    Medians include only completed jobs with a valid measurement and report their sample
    size. ``experimental`` lists experiment records separately from production statistics.
    """
    return build_dashboard_summary()
