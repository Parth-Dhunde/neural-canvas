"""Reconstruction engine factory."""

from __future__ import annotations

from app.engines.reconstruction.base import ReconstructionEngine
from app.engines.reconstruction.custom_nerf import CustomNeRFReconstructionEngine
from app.engines.reconstruction.instant_ngp import InstantNGPReconstructionEngine
from app.models.job import Job

_ENGINE_ALIASES = {
    "instant-ngp": "Instant-NGP",
    "instant_ngp": "Instant-NGP",
    "custom-nerf": "Custom NeRF",
    "custom_nerf": "Custom NeRF",
}


def normalize_engine_name(engine: str) -> str:
    """Return the canonical engine identifier for ``engine``."""
    return _ENGINE_ALIASES.get(engine, engine)


def get_reconstruction_engine(job: Job) -> ReconstructionEngine:
    """Return the reconstruction engine implementation for a job."""
    engine_name = normalize_engine_name(job.engine)
    if engine_name == "Instant-NGP":
        return InstantNGPReconstructionEngine()
    if engine_name == "Custom NeRF":
        return CustomNeRFReconstructionEngine()
    raise ValueError(f"Unsupported reconstruction engine: {job.engine}")
