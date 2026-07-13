"""3D viewer asset endpoints (not implemented)."""

from fastapi import APIRouter

router = APIRouter(prefix="/viewer", tags=["viewer"])

# Future: mesh preview, asset metadata, export URLs
