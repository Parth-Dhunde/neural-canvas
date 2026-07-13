"""Mesh generation engine factory."""

from __future__ import annotations

from app.engines.mesh_generation.base import MeshGenerationEngine
from app.engines.mesh_generation.instant_ngp_mesh import InstantNGPMeshGenerationEngine
from app.engines.reconstruction.factory import normalize_engine_name
from app.models.job import Job


def get_mesh_generation_engine(job: Job) -> MeshGenerationEngine:
    """Return the mesh generation engine implementation for a job."""
    engine_name = normalize_engine_name(job.engine)
    if engine_name == "Instant-NGP":
        return InstantNGPMeshGenerationEngine()
    if engine_name == "Custom NeRF":
        raise ValueError("Mesh generation is not implemented for Custom NeRF yet.")
    raise ValueError(f"Unsupported mesh generation engine: {job.engine}")

