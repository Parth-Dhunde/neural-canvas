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

    app_name: str = Field(default="NeuralCanvas", alias="APP_NAME")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    jobs_root: Path = Field(default=Path("jobs"), alias="JOBS_ROOT")
    datasets_root: Path = Field(default=Path("datasets"), alias="DATASETS_ROOT")
    engines_root: Path = Field(default=Path("engines"), alias="ENGINES_ROOT")
    models_root: Path = Field(default=Path("models"), alias="MODELS_ROOT")
    outputs_root: Path = Field(default=Path("outputs"), alias="OUTPUTS_ROOT")

    colmap_binary: str = Field(default="colmap", alias="COLMAP_BINARY")
    colmap_use_gpu: bool = Field(default=False, alias="COLMAP_USE_GPU")
    colmap_camera_model: str = Field(default="OPENCV", alias="COLMAP_CAMERA_MODEL")

    instant_ngp_root: Path = Field(default=Path("engines/instant-ngp"), alias="INSTANT_NGP_ROOT")
    instant_ngp_python: str = Field(default="python3", alias="INSTANT_NGP_PYTHON")
    instant_ngp_n_steps: int = Field(default=35000, alias="INSTANT_NGP_N_STEPS")

    mesh_resolution: int = Field(default=256, alias="MESH_RESOLUTION")
    mesh_density_threshold: float = Field(default=2.5, alias="MESH_DENSITY_THRESHOLD")

    @property
    def jobs_path(self) -> Path:
        return resolve_workspace_path(self.jobs_root)

    @property
    def datasets_path(self) -> Path:
        return resolve_workspace_path(self.datasets_root)

    @property
    def engines_path(self) -> Path:
        return resolve_workspace_path(self.engines_root)

    @property
    def models_path(self) -> Path:
        return resolve_workspace_path(self.models_root)

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
