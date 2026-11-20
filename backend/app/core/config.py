"""Application settings loaded from environment variables and ``.env``."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import get_workspace_root, resolve_workspace_path


class Settings(BaseSettings):
    """Runtime configuration for the NeuralCanvas backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # The bind address and port are set by the `uvicorn --host/--port` flags, not here.
    app_name: str = Field(default="NeuralCanvas", alias="APP_NAME")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    jobs_root: Path = Field(default=Path("jobs"), alias="JOBS_ROOT")
    # Only read for experiment records (outputs/experiments/*/*/metrics.json) on the dashboard.
    outputs_root: Path = Field(default=Path("outputs"), alias="OUTPUTS_ROOT")

    colmap_binary: str = Field(default="colmap", alias="COLMAP_BINARY")
    colmap_use_gpu: bool = Field(default=False, alias="COLMAP_USE_GPU")
    colmap_camera_model: str = Field(default="OPENCV", alias="COLMAP_CAMERA_MODEL")
    # Minimum fraction of eligible (masked) images COLMAP must register for stage 3 to pass.
    colmap_min_registration_ratio: float = Field(
        default=0.5, ge=0.0, le=1.0, alias="COLMAP_MIN_REGISTRATION_RATIO"
    )

    instant_ngp_root: Path = Field(default=Path("engines/instant-ngp"), alias="INSTANT_NGP_ROOT")
    instant_ngp_python: str = Field(default="python3", alias="INSTANT_NGP_PYTHON")
    instant_ngp_n_steps: int = Field(default=35000, alias="INSTANT_NGP_N_STEPS")

    mesh_resolution: int = Field(default=256, alias="MESH_RESOLUTION")
    mesh_density_threshold: float = Field(default=2.5, alias="MESH_DENSITY_THRESHOLD")

    # Mesh cleanup (stage 6). Taubin requires 0 < 1/lambda - 1/nu < 0.1 (checked at run time).
    mesh_cleanup_taubin_iterations: int = Field(
        default=10, ge=0, le=100, alias="MESH_CLEANUP_TAUBIN_ITERATIONS"
    )
    mesh_cleanup_taubin_lambda: float = Field(
        default=0.33, gt=0.0, le=1.0, alias="MESH_CLEANUP_TAUBIN_LAMBDA"
    )
    mesh_cleanup_taubin_nu: float = Field(default=0.34, gt=0.0, le=1.0, alias="MESH_CLEANUP_TAUBIN_NU")
    # Disconnected pieces with fewer faces are left unsmoothed (Taubin only shrinks them).
    mesh_cleanup_smooth_min_component_faces: int = Field(
        default=60, ge=0, alias="MESH_CLEANUP_SMOOTH_MIN_COMPONENT_FACES"
    )
    # Disconnected pieces with fewer faces are removed as noise (an isolated marching-cubes
    # cell closes with 8 faces); 0 disables floater removal.
    mesh_cleanup_min_component_faces: int = Field(
        default=12, ge=0, alias="MESH_CLEANUP_MIN_COMPONENT_FACES"
    )
    # Meshes at or below this face count are not decimated; larger ones get an adaptive target
    # of sqrt(faces * min_faces), clamped to [min_faces, max_faces].
    mesh_cleanup_decimate_min_faces: int = Field(
        default=50_000, ge=1_000, alias="MESH_CLEANUP_DECIMATE_MIN_FACES"
    )
    mesh_cleanup_decimate_max_faces: int = Field(
        default=250_000, ge=1_000, alias="MESH_CLEANUP_DECIMATE_MAX_FACES"
    )

    @property
    def jobs_path(self) -> Path:
        return resolve_workspace_path(self.jobs_root)

    @property
    def outputs_path(self) -> Path:
        return resolve_workspace_path(self.outputs_root)

    @property
    def workspace_path(self) -> Path:
        return get_workspace_root()

    @property
    def instant_ngp_path(self) -> Path:
        if self.instant_ngp_root.is_absolute():
            return self.instant_ngp_root
        return resolve_workspace_path(self.instant_ngp_root)


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
