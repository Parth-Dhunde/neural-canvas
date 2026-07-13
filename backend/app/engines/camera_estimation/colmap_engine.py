"""COLMAP-backed camera estimation engine."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.engines.camera_estimation.base import (
    CameraEstimationEngine,
    CameraEstimationResult,
    ControlCallback,
    LogCallback,
    ProgressCallback,
)
from app.engines.camera_estimation.transforms_export import export_transforms_json
from app.jobs.repository import JobRepository
from app.jobs.structure import (
    MASKED_IMAGES_DIR,
    SUPPORTED_IMAGE_EXTENSIONS,
    camera_database_path,
    camera_path,
    camera_sparse_path,
    camera_transforms_file,
    camera_transforms_relative_path,
    job_root_path,
    masked_images_path,
)
from app.models.job import Job

logger = get_logger(__name__)

MIN_MASKED_IMAGES = 2


class ColmapCameraEstimationEngine(CameraEstimationEngine):
    """Estimate camera poses using the COLMAP CLI."""

    name = "colmap"

    def __init__(
        self,
        settings: Settings | None = None,
        repository: JobRepository | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._repository = repository or JobRepository()

    def validate(self, job: Job) -> CameraEstimationResult:
        if shutil.which(self._settings.colmap_binary) is None:
            return CameraEstimationResult(
                success=False,
                message=(
                    f"COLMAP is unavailable. Install COLMAP or set COLMAP_BINARY "
                    f"to the executable path. Attempted: {self._settings.colmap_binary!r}"
                ),
                error_code="COLMAP_UNAVAILABLE",
            )

        image_count = self._count_masked_images(job.id)
        if image_count < MIN_MASKED_IMAGES:
            return CameraEstimationResult(
                success=False,
                message=(
                    f"At least {MIN_MASKED_IMAGES} masked images are required for camera "
                    f"estimation. Found {image_count}."
                ),
                error_code="VALIDATION_FAILED",
            )

        return CameraEstimationResult(
            success=True,
            message="Validation passed.",
            data={"masked_image_count": image_count},
        )

    def estimate(
        self,
        job: Job,
        *,
        log: LogCallback | None = None,
        on_progress: ProgressCallback | None = None,
        check_control: ControlCallback | None = None,
    ) -> CameraEstimationResult:
        validation = self.validate(job)
        if not validation.success:
            return validation

        jobs_root = self._repository.jobs_root
        job_root = job_root_path(jobs_root, job.id)
        masked_dir = masked_images_path(jobs_root, job.id)
        camera_dir = camera_path(jobs_root, job.id)
        database_path = camera_database_path(jobs_root, job.id)
        sparse_dir = camera_sparse_path(jobs_root, job.id)
        transforms_path = camera_transforms_file(jobs_root, job.id)

        camera_dir.mkdir(parents=True, exist_ok=True)
        sparse_dir.mkdir(parents=True, exist_ok=True)
        transforms_path.parent.mkdir(parents=True, exist_ok=True)

        if database_path.exists():
            database_path.unlink()

        emit = _make_logger(log)
        progress = on_progress or (lambda _value: None)
        check = check_control or (lambda: None)

        try:
            check()
            emit("Extracting features...")
            self._run_colmap(
                "feature_extractor",
                [
                    "--database_path",
                    str(database_path),
                    "--image_path",
                    str(masked_dir),
                    "--ImageReader.camera_model",
                    self._settings.colmap_camera_model,
                    "--ImageReader.single_camera",
                    "1",
                ],
            )
            progress(25)

            check()
            emit("Matching images...")
            self._run_colmap(
                "exhaustive_matcher",
                [
                    "--database_path",
                    str(database_path),
                ],
            )
            progress(50)

            check()
            emit("Sparse reconstruction...")
            self._run_colmap(
                "mapper",
                [
                    "--database_path",
                    str(database_path),
                    "--image_path",
                    str(masked_dir),
                    "--output_path",
                    str(sparse_dir),
                ],
            )
            progress(80)

            sparse_model = self._resolve_sparse_model(sparse_dir)
            if sparse_model is None:
                return CameraEstimationResult(
                    success=False,
                    message="COLMAP sparse reconstruction produced no model.",
                    error_code="SPARSE_RECONSTRUCTION_FAILED",
                )

            check()
            emit("Exporting transforms...")
            text_model_dir = sparse_model
            cameras_txt = text_model_dir / "cameras.txt"
            images_txt = text_model_dir / "images.txt"
            if not cameras_txt.is_file() or not images_txt.is_file():
                self._run_colmap(
                    "model_converter",
                    [
                        "--input_path",
                        str(sparse_model),
                        "--output_path",
                        str(text_model_dir),
                        "--output_type",
                        "TXT",
                    ],
                )

            document = export_transforms_json(
                cameras_txt=cameras_txt,
                images_txt=images_txt,
                output_path=transforms_path,
            )
            progress(100)

            relative_transforms = camera_transforms_relative_path()
            return CameraEstimationResult(
                success=True,
                message="Camera estimation complete.",
                transforms_path=relative_transforms,
                registered_images=len(document.get("frames", [])),
                data={
                    "database_path": str(database_path.relative_to(job_root)),
                    "sparse_path": str(sparse_model.relative_to(job_root)),
                    "transforms_path": relative_transforms,
                    "masked_images_dir": MASKED_IMAGES_DIR,
                },
            )
        except _ColmapExecutionError as exc:
            emit(str(exc), level="error")
            return CameraEstimationResult(
                success=False,
                message=str(exc),
                error_code=exc.error_code,
            )
        except Exception as exc:
            logger.exception("Camera estimation failed | job_id=%s", job.id)
            emit(f"Camera estimation failed: {exc}", level="error")
            return CameraEstimationResult(
                success=False,
                message=str(exc),
                error_code="CAMERA_ESTIMATION_FAILED",
            )

    def _count_masked_images(self, job_id: str) -> int:
        directory = masked_images_path(self._repository.jobs_root, job_id)
        if not directory.is_dir():
            return 0
        return sum(
            1
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        )

    def _run_colmap(self, command: str, args: list[str]) -> None:
        binary = self._settings.colmap_binary
        full_command = [binary, command, *args]
        if self._settings.colmap_use_gpu and command in {"feature_extractor", "exhaustive_matcher"}:
            if command == "feature_extractor":
                full_command.extend(["--SiftExtraction.use_gpu", "1"])
            if command == "exhaustive_matcher":
                full_command.extend(["--SiftMatching.use_gpu", "1"])

        logger.info("Running COLMAP | command=%s", " ".join(full_command))
        completed = subprocess.run(
            full_command,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            error_code = _error_code_for_command(command)
            stderr = completed.stderr.strip() or completed.stdout.strip() or "Unknown COLMAP error"
            raise _ColmapExecutionError(
                f"COLMAP {command} failed: {stderr}",
                error_code=error_code,
            )

    @staticmethod
    def _resolve_sparse_model(sparse_dir: Path) -> Path | None:
        if not sparse_dir.is_dir():
            return None
        candidates = sorted(path for path in sparse_dir.iterdir() if path.is_dir())
        if not candidates:
            return None
        return candidates[0]


class _ColmapExecutionError(RuntimeError):
    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


def _error_code_for_command(command: str) -> str:
    mapping = {
        "feature_extractor": "FEATURE_EXTRACTION_FAILED",
        "exhaustive_matcher": "MATCHING_FAILED",
        "mapper": "SPARSE_RECONSTRUCTION_FAILED",
        "model_converter": "TRANSFORM_EXPORT_FAILED",
    }
    return mapping.get(command, "CAMERA_ESTIMATION_FAILED")


def _make_logger(log: LogCallback | None) -> Callable[[str, str], None]:
    def emit(message: str, level: str = "info") -> None:
        if log is None:
            return
        try:
            log(message, level)
        except TypeError:
            log(message)

    return emit
