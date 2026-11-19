"""Tests for COLMAP camera estimation failure handling."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.engines.camera_estimation.colmap_engine import ColmapCameraEstimationEngine
from app.models.job import Job


@pytest.fixture
def engine(tmp_path: Path) -> ColmapCameraEstimationEngine:
    colmap_binary = tmp_path / "colmap"
    colmap_binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    colmap_binary.chmod(0o755)

    settings = Settings(
        COLMAP_BINARY=str(colmap_binary),
        COLMAP_USE_GPU=False,
        COLMAP_CAMERA_MODEL="OPENCV",
        JOBS_ROOT=str(tmp_path / "jobs"),
    )
    from app.jobs.repository import JobRepository

    repository = JobRepository(settings=settings)
    job_id = "job_000099"
    repository.create_folder_structure(job_id)
    masked_dir = tmp_path / "jobs" / job_id / "masked_images"
    masked_dir.mkdir(parents=True, exist_ok=True)
    (masked_dir / "a.png").write_bytes(b"fake")
    (masked_dir / "b.png").write_bytes(b"fake")

    return ColmapCameraEstimationEngine(settings=settings, repository=repository)


def test_mapper_no_initial_pair_fails_before_transform_export(engine: ColmapCameraEstimationEngine) -> None:
    job = Job(id="job_000099", name="test", engine="Instant-NGP")

    def fake_run_colmap(command: str, args: list[str], *, emit, check) -> list[str]:
        check()
        if command == "mapper":
            return [
                "Finding good initial image pair",
                "=> No good initial image pair found.",
                "Discarding reconstruction due to no initial pair",
            ]
        return []

    with patch.object(engine, "_run_colmap", side_effect=fake_run_colmap):
        result = engine.estimate(job)

    assert result.success is False
    assert result.error_code == "SPARSE_RECONSTRUCTION_FAILED"
    assert "no good initial image pair found" in result.message.lower()

    transforms = (
        Path(engine._repository.jobs_root)
        / "job_000099"
        / "camera"
        / "transforms"
        / "transforms.json"
    )
    assert not transforms.is_file()


def test_valid_sparse_model_can_export_transforms(tmp_path: Path) -> None:
    from app.engines.camera_estimation.transforms_export import export_transforms_json

    cameras_txt = tmp_path / "cameras.txt"
    images_txt = tmp_path / "images.txt"
    output_path = tmp_path / "transforms.json"

    cameras_txt.write_text("1 PINHOLE 640 480 800.0 800.0 320.0 240.0\n", encoding="utf-8")
    images_txt.write_text(
        "1 1 0 0 0 0 0 0 1 image_a.png\n\n2 1 0 0 0 1 0 0 1 image_b.png\n\n",
        encoding="utf-8",
    )

    document = export_transforms_json(
        cameras_txt=cameras_txt,
        images_txt=images_txt,
        output_path=output_path,
    )
    assert output_path.is_file()
    assert len(document["frames"]) == 2
