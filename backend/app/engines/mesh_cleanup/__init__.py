"""Mesh cleanup engine implementations."""

from app.engines.mesh_cleanup.base import MeshCleanupEngine, MeshCleanupResult
from app.engines.mesh_cleanup.trimesh_cleanup import TrimeshMeshCleanupEngine


def get_mesh_cleanup_engine() -> MeshCleanupEngine:
    """Return the configured mesh cleanup engine implementation."""
    return TrimeshMeshCleanupEngine()


__all__ = ["MeshCleanupEngine", "MeshCleanupResult", "get_mesh_cleanup_engine"]
