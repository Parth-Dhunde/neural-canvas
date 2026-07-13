"""Camera estimation engine implementations."""

from app.engines.camera_estimation.base import CameraEstimationEngine, CameraEstimationResult
from app.engines.camera_estimation.colmap_engine import ColmapCameraEstimationEngine


def get_camera_estimation_engine() -> CameraEstimationEngine:
    """Return the configured camera estimation engine implementation."""
    return ColmapCameraEstimationEngine()
