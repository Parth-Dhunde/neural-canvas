"""Background removal engine implementations."""

from app.engines.background_removal.base import BackgroundRemovalEngine
from app.engines.background_removal.rembg_engine import RemBGBackgroundRemovalEngine


def get_background_removal_engine() -> BackgroundRemovalEngine:
    """Return the configured background removal engine implementation."""
    return RemBGBackgroundRemovalEngine()
