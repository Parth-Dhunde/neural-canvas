"""Tests for COLMAP sparse-model selection, registration ratio, and stale-output handling."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.engines.camera_estimation.colmap_engine import ColmapCameraEstimationEngine
from app.jobs.repository import JobRepository
from app.models.job import Job

JOB_ID = "job_000099"


def _image_names(count: int, *, offset: int = 0) -> list[str]:
    return [f"r_{index}.png" for index in range(offset, offset + count)]


def _write_text_model(model_dir: Path, names: list[str]) -> None:
    """Write a minimal COLMAP text model registering ``names``."""
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "cameras.txt").write_text(
        "# Camera list\n1 PINHOLE 800 800 1000.0 1000.0 400.0 400.0\n",
        encoding="utf-8",
    )
    lines = ["# Image list"]
    for image_id, name in enumerate(names, start=1):
        lines.append(f"{image_id} 1 0 0 0 0 0 {image_id} 1 {name}")
        lines.append("")
    (model_dir / "images.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_engine(
    tmp_path: Path,
    *,
    masked_images: int,
    min_ratio: float = 0.5,
) -> ColmapCameraEstimationEngine:
    colmap_binary = tmp_path / "colmap"
    colmap_binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    colmap_binary.chmod(0o755)

    settings = Settings(
        COLMAP_BINARY=str(colmap_binary),
        COLMAP_USE_GPU=False,
        COLMAP_CAMERA_MODEL="OPENCV",
        COLMAP_MIN_REGISTRATION_RATIO=min_ratio,
        JOBS_ROOT=str(tmp_path / "jobs"),
    )
    repository = JobRepository(settings=settings)
    repository.create_folder_structure(JOB_ID)
    masked_dir = repository.jobs_root / JOB_ID / "masked_images"
    for name in _image_names(masked_images):
        (masked_dir / name).write_bytes(b"fake")

    return ColmapCameraEstimationEngine(settings=settings, repository=repository)


def _camera_dir(engine: ColmapCameraEstimationEngine) -> Path:
    return engine._repository.jobs_root / JOB_ID / "camera"


def _run_with_mapper_models(
    engine: ColmapCameraEstimationEngine,
    models: dict[str, list[str] | None],
    *,
    mapper_output: list[str] | None = None,
    on_mapper=None,
):
    """Run ``estimate`` with a fake COLMAP whose mapper writes ``models``.

    A ``None`` model value creates an empty directory; a list writes a text model.
    """
    sparse_dir = _camera_dir(engine) / "sparse"

    def fake_run_colmap(command: str, args: list[str], *, emit, check) -> list[str]:
        check()
        if command == "mapper":
            if on_mapper is not None:
                on_mapper(sparse_dir)
            for name, names in models.items():
                if names is None:
                    (sparse_dir / name).mkdir(parents=True, exist_ok=True)
                else:
                    _write_text_model(sparse_dir / name, names)
            return list(mapper_output or [])
        if command == "model_converter":
            raise AssertionError("text models should not need conversion")
        return []

    logs: list[str] = []
    job = Job(id=JOB_ID, name="test", engine="Instant-NGP")
    with patch.object(engine, "_run_colmap", side_effect=fake_run_colmap):
        result = engine.estimate(job, log=lambda message, level="info": logs.append(message))
    return result, logs


def _transforms(engine: ColmapCameraEstimationEngine) -> dict | None:
    path = _camera_dir(engine) / "transforms" / "transforms.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _frame_names(document: dict) -> set[str]:
    return {Path(frame["file_path"]).name for frame in document["frames"]}


def test_selects_sparse_1_with_97_images_over_sparse_0_with_2(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path, masked_images=100)
    model_0 = ["r_67.png", "r_9.png"]
    model_1 = _image_names(97)

    result, logs = _run_with_mapper_models(engine, {"0": model_0, "1": model_1})

    assert result.success is True, result.message
    assert result.registered_images == 97
    assert result.data["sparse_path"] == "camera/sparse/1"
    assert result.data["eligible_images"] == 100

    document = _transforms(engine)
    assert document is not None
    assert len(document["frames"]) == 97
    assert _frame_names(document) == set(model_1)
    assert any("Selected sparse model 1: 97/100" in line for line in logs)


def test_selects_model_with_most_registered_images_among_several(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path, masked_images=20)
    models = {
        "0": _image_names(5),
        "1": _image_names(16, offset=2),
        "2": _image_names(11),
    }

    result, _ = _run_with_mapper_models(engine, models)

    assert result.success is True, result.message
    assert result.registered_images == 16
    assert result.data["sparse_path"] == "camera/sparse/1"
    assert _frame_names(_transforms(engine)) == set(models["1"])


def test_usable_model_wins_over_no_initial_pair_log(tmp_path: Path) -> None:
    """COLMAP logs this when it cannot start a second model after a good first one."""
    engine = _make_engine(tmp_path, masked_images=10)

    result, _ = _run_with_mapper_models(
        engine,
        {"0": _image_names(9)},
        mapper_output=["=> No good initial image pair found."],
    )

    assert result.success is True, result.message
    assert result.registered_images == 9


def test_fails_when_registration_ratio_below_threshold(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path, masked_images=100)

    result, logs = _run_with_mapper_models(engine, {"0": _image_names(40)})

    assert result.success is False
    assert result.error_code == "INSUFFICIENT_REGISTRATION"
    assert "40/100" in result.message
    assert "50%" in result.message
    assert _transforms(engine) is None
    assert any("40/100" in line for line in logs)


def test_registration_threshold_is_configurable(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path, masked_images=100, min_ratio=0.3)

    result, _ = _run_with_mapper_models(engine, {"0": _image_names(40)})

    assert result.success is True, result.message
    assert result.registered_images == 40


def test_stale_sparse_models_and_transforms_are_cleared_before_mapper(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path, masked_images=100)
    camera_dir = _camera_dir(engine)
    # Leftovers from an earlier attempt: a larger stale model and stale transforms.
    _write_text_model(camera_dir / "sparse" / "1", _image_names(97))
    stale_transforms = camera_dir / "transforms" / "transforms.json"
    stale_transforms.parent.mkdir(parents=True, exist_ok=True)
    stale_transforms.write_text('{"frames": ["stale"]}', encoding="utf-8")
    unrelated = camera_dir / "database_test_cli.db"
    unrelated.write_bytes(b"keep")
    historical_mesh = engine._repository.jobs_root / JOB_ID / "meshes" / "old_run" / "mesh.glb"
    historical_mesh.parent.mkdir(parents=True)
    historical_mesh.write_bytes(b"glb")

    seen_at_mapper: dict[str, object] = {}

    def on_mapper(sparse_dir: Path) -> None:
        seen_at_mapper["sparse_children"] = sorted(p.name for p in sparse_dir.iterdir())
        seen_at_mapper["transforms_exists"] = stale_transforms.exists()

    fresh = _image_names(60, offset=40)
    result, _ = _run_with_mapper_models(engine, {"0": fresh}, on_mapper=on_mapper)

    assert seen_at_mapper == {"sparse_children": [], "transforms_exists": False}
    assert result.success is True, result.message
    assert result.registered_images == 60
    assert result.data["sparse_path"] == "camera/sparse/0"
    assert _frame_names(_transforms(engine)) == set(fresh)
    assert not (camera_dir / "sparse" / "1").exists()
    assert unrelated.read_bytes() == b"keep"
    assert historical_mesh.read_bytes() == b"glb"


def test_missing_sparse_models_fail_clearly(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path, masked_images=10)

    result, _ = _run_with_mapper_models(engine, {})

    assert result.success is False
    assert result.error_code == "SPARSE_RECONSTRUCTION_FAILED"
    assert "0/10" in result.message
    assert _transforms(engine) is None


def test_missing_sparse_directory_fails_clearly(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path, masked_images=10)

    def remove_sparse_dir(sparse_dir: Path) -> None:
        sparse_dir.rmdir()

    result, _ = _run_with_mapper_models(engine, {}, on_mapper=remove_sparse_dir)

    assert result.success is False
    assert result.error_code == "SPARSE_RECONSTRUCTION_FAILED"
    assert _transforms(engine) is None


def test_empty_and_malformed_models_are_skipped(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path, masked_images=4)
    sparse_dir = _camera_dir(engine) / "sparse"

    def write_malformed(_: Path) -> None:
        bad = sparse_dir / "1"
        bad.mkdir(parents=True)
        (bad / "cameras.txt").write_text("1 PINHOLE 800 800 1 1 1 1\n", encoding="utf-8")
        (bad / "images.txt").write_text("1 2 3\n\ngarbage line\n", encoding="utf-8")

    result, logs = _run_with_mapper_models(
        engine,
        {"0": None, "2": _image_names(3)},
        on_mapper=write_malformed,
    )

    assert result.success is True, result.message
    assert result.registered_images == 3
    assert result.data["sparse_path"] == "camera/sparse/2"
    assert any("Skipping sparse model 0" in line for line in logs)


def test_only_invalid_models_fail_without_transforms(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path, masked_images=4)

    result, _ = _run_with_mapper_models(engine, {"0": None, "1": ["r_0.png"]})

    assert result.success is False
    assert result.error_code == "SPARSE_RECONSTRUCTION_FAILED"
    assert _transforms(engine) is None


@pytest.mark.parametrize("ratio", [-0.1, 1.5])
def test_registration_ratio_setting_is_bounded(ratio: float) -> None:
    with pytest.raises(ValueError):
        Settings(COLMAP_MIN_REGISTRATION_RATIO=ratio)
