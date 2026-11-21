"""System status API routes."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.services.system_status import get_last_validation, run_startup_validation

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/engines")
async def get_engine_status() -> dict[str, object]:
    """Return installation and readiness status for reconstruction engines."""
    result = get_last_validation() or run_startup_validation()
    return result.to_api_dict()


@router.get("/config")
async def get_pipeline_config() -> dict[str, object]:
    """Read-only reconstruction parameters from the backend configuration.

    Only numeric and categorical pipeline parameters are returned; paths, binaries and other
    host details are deliberately left out.
    """
    s = get_settings()
    return {
        "source": "backend environment (backend/.env)",
        "camera_estimation": {
            "camera_model": s.colmap_camera_model,
            "use_gpu": s.colmap_use_gpu,
            "min_registration_ratio": s.colmap_min_registration_ratio,
        },
        "training": {"n_steps": s.instant_ngp_n_steps},
        "mesh": {
            "resolution": s.mesh_resolution,
            "density_threshold": s.mesh_density_threshold,
        },
        "mesh_cleanup": {
            "taubin_iterations": s.mesh_cleanup_taubin_iterations,
            "taubin_lambda": s.mesh_cleanup_taubin_lambda,
            "taubin_nu": s.mesh_cleanup_taubin_nu,
            "min_component_faces": s.mesh_cleanup_min_component_faces,
            "smooth_min_component_faces": s.mesh_cleanup_smooth_min_component_faces,
            "decimate_min_faces": s.mesh_cleanup_decimate_min_faces,
            "decimate_max_faces": s.mesh_cleanup_decimate_max_faces,
        },
        "export_formats": ["glb", "obj", "ply"],
        "stages_always_run": [
            "Upload",
            "Background Removal",
            "Camera Estimation",
            "Reconstruction",
            "Mesh Generation",
            "Mesh Cleanup",
            "Export",
        ],
    }
