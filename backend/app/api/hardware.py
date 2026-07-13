"""Hardware metrics endpoints (not implemented)."""

from fastapi import APIRouter

router = APIRouter(prefix="/hardware", tags=["hardware"])

# Future: GET /hardware, GET /jobs/{id}/hardware
