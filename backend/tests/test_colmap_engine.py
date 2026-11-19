"""Tests for COLMAP camera estimation command construction."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.engines.camera_estimation.colmap_engine import ColmapCameraEstimationEngine


@pytest.fixture
def colmap_binary(tmp_path: Path) -> Path:
    binary = tmp_path / "colmap"
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    return binary


def test_build_command_uses_configured_binary(colmap_binary: Path) -> None:
    settings = Settings(
        COLMAP_BINARY=str(colmap_binary),
        COLMAP_USE_GPU=False,
        COLMAP_CAMERA_MODEL="OPENCV",
    )
    engine = ColmapCameraEstimationEngine(settings=settings)

    command = engine.build_command(
        "feature_extractor",
        [
            "--database_path",
            "/tmp/database.db",
            "--image_path",
            "/tmp/images",
            "--ImageReader.camera_model",
            "OPENCV",
            "--ImageReader.single_camera",
            "1",
        ],
    )

    assert command[0] == str(colmap_binary.resolve())
    assert command[1] == "feature_extractor"
    assert "--FeatureExtraction.use_gpu" in command
    assert command[command.index("--FeatureExtraction.use_gpu") + 1] == "0"


def test_build_command_enables_gpu_when_configured(colmap_binary: Path) -> None:
    settings = Settings(
        COLMAP_BINARY=str(colmap_binary),
        COLMAP_USE_GPU=True,
        COLMAP_CAMERA_MODEL="OPENCV",
    )
    engine = ColmapCameraEstimationEngine(settings=settings)

    command = engine.build_command("exhaustive_matcher", ["--database_path", "/tmp/database.db"])

    assert "--FeatureMatching.use_gpu" in command
    assert command[command.index("--FeatureMatching.use_gpu") + 1] == "1"


def test_validate_rejects_missing_binary() -> None:
    settings = Settings(
        COLMAP_BINARY="/definitely/missing/colmap",
        COLMAP_USE_GPU=False,
        COLMAP_CAMERA_MODEL="OPENCV",
    )
    engine = ColmapCameraEstimationEngine(settings=settings)

    from app.models.job import Job

    job = Job(id="job_test", name="test", engine="instant-ngp")
    result = engine.validate(job)

    assert result.success is False
    assert result.error_code == "COLMAP_UNAVAILABLE"
