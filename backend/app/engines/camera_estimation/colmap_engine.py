"""COLMAP-backed camera estimation engine."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from app.core.config import Settings, get_settings
from app.core.text import strip_ansi
from app.core.logging import get_logger
from app.engines.camera_estimation.base import (
    CameraEstimationEngine,
    CameraEstimationResult,
    ControlCallback,
    LogCallback,
    ProgressCallback,
)
from app.engines.camera_estimation.colmap_validation import (
    MIN_REGISTERED_IMAGES,
    infer_mapper_failure_message,
    reconstruction_failure_message,
    registered_image_count,
    registration_ratio_failure_message,
    sparse_model_has_files,
    sparse_model_is_usable,
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
from app.pipeline.pipeline_manager import PipelineControlError

logger = get_logger(__name__)

MIN_MASKED_IMAGES = 2
SPARSE_TEXT_DIR = "model_text"


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
        binary_error = self._binary_validation_error()
        if binary_error is not None:
            return binary_error

        masked_dir = masked_images_path(self._repository.jobs_root, job.id)
        if not masked_dir.is_dir():
            return CameraEstimationResult(
                success=False,
                message=(
                    f"Masked images directory not found: {masked_dir}. "
                    "Complete background removal before camera estimation."
                ),
                error_code="VALIDATION_FAILED",
            )

        image_count = self._count_images(masked_dir)
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
        text_model_dir = camera_dir / SPARSE_TEXT_DIR
        eligible_images = int(validation.data.get("masked_image_count", 0))

        # A fresh run must not select sparse models or reuse transforms from an earlier attempt.
        if database_path.exists():
            database_path.unlink()
        if text_model_dir.exists():
            shutil.rmtree(text_model_dir)
        if sparse_dir.exists():
            shutil.rmtree(sparse_dir)
        if transforms_path.exists():
            transforms_path.unlink()

        camera_dir.mkdir(parents=True, exist_ok=True)
        sparse_dir.mkdir(parents=True, exist_ok=True)
        transforms_path.parent.mkdir(parents=True, exist_ok=True)

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
                emit=emit,
                check=check,
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
                emit=emit,
                check=check,
            )
            progress(50)

            check()
            emit("Sparse reconstruction...")
            mapper_output = self._run_colmap(
                "mapper",
                [
                    "--database_path",
                    str(database_path),
                    "--image_path",
                    str(masked_dir),
                    "--output_path",
                    str(sparse_dir),
                ],
                emit=emit,
                check=check,
            )
            progress(75)

            # The mapper may log "no good initial image pair" while failing to start an
            # additional model after a good one, so usable models take precedence over logs.
            sparse_model, registered_images = self._find_best_sparse_model(
                sparse_dir=sparse_dir,
                text_model_dir=text_model_dir,
                emit=emit,
                check=check,
            )
            if sparse_model is None or registered_images < MIN_REGISTERED_IMAGES:
                message = reconstruction_failure_message(
                    mapper_output=mapper_output,
                    registered_images=registered_images,
                )
                if sparse_model is None and infer_mapper_failure_message(mapper_output):
                    message = infer_mapper_failure_message(mapper_output) or message
                message = (
                    f"{message} Registered {registered_images}/{eligible_images} "
                    "eligible images."
                )
                emit(message, level="error")
                return CameraEstimationResult(
                    success=False,
                    message=message,
                    error_code="SPARSE_RECONSTRUCTION_FAILED",
                    registered_images=registered_images,
                    data={"eligible_images": eligible_images},
                )

            emit(
                f"Selected sparse model {sparse_model.name}: "
                f"{registered_images}/{eligible_images} eligible images registered."
            )
            ratio_failure = registration_ratio_failure_message(
                registered_images=registered_images,
                eligible_images=eligible_images,
                min_ratio=self._settings.colmap_min_registration_ratio,
            )
            if ratio_failure is not None:
                emit(ratio_failure, level="error")
                return CameraEstimationResult(
                    success=False,
                    message=ratio_failure,
                    error_code="INSUFFICIENT_REGISTRATION",
                    registered_images=registered_images,
                    data={
                        "eligible_images": eligible_images,
                        "sparse_path": str(sparse_model.relative_to(job_root)),
                    },
                )

            check()
            emit("Exporting transforms...")
            cameras_txt, images_txt = self._resolve_model_text_files(
                sparse_model=sparse_model,
                text_model_dir=text_model_dir,
                emit=emit,
                check=check,
            )

            document = export_transforms_json(
                cameras_txt=cameras_txt,
                images_txt=images_txt,
                output_path=transforms_path,
            )

            if not transforms_path.is_file():
                return CameraEstimationResult(
                    success=False,
                    message="transforms.json was not created.",
                    error_code="TRANSFORM_EXPORT_FAILED",
                )

            exported_frames = len(document.get("frames", []))
            if exported_frames != registered_images:
                transforms_path.unlink(missing_ok=True)
                message = (
                    f"transforms.json has {exported_frames} frame(s) but selected sparse model "
                    f"{sparse_model.name} has {registered_images} registered image(s)."
                )
                emit(message, level="error")
                return CameraEstimationResult(
                    success=False,
                    message=message,
                    error_code="TRANSFORM_EXPORT_FAILED",
                )

            progress(100)

            relative_transforms = camera_transforms_relative_path()
            return CameraEstimationResult(
                success=True,
                message="Camera estimation complete.",
                transforms_path=relative_transforms,
                registered_images=registered_images,
                data={
                    "database_path": str(database_path.relative_to(job_root)),
                    "sparse_path": str(sparse_model.relative_to(job_root)),
                    "transforms_path": relative_transforms,
                    "masked_images_dir": MASKED_IMAGES_DIR,
                    "eligible_images": eligible_images,
                },
            )
        except PipelineControlError:
            raise
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

    def build_command(self, command: str, args: list[str]) -> list[str]:
        """Build the full COLMAP CLI invocation for testing and logging."""
        return self._build_colmap_command(command, args)

    def _binary_validation_error(self) -> CameraEstimationResult | None:
        binary = self._resolve_colmap_binary()
        if binary is not None:
            return None
        configured = self._settings.colmap_binary
        return CameraEstimationResult(
            success=False,
            message=(
                f"COLMAP is unavailable. Install COLMAP or set COLMAP_BINARY "
                f"to an executable path. Attempted: {configured!r}"
            ),
            error_code="COLMAP_UNAVAILABLE",
        )

    def _resolve_colmap_binary(self) -> Path | None:
        candidate = Path(self._settings.colmap_binary)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()

        discovered = shutil.which(self._settings.colmap_binary)
        if discovered is not None:
            path = Path(discovered)
            if path.is_file() and os.access(path, os.X_OK):
                return path.resolve()
        return None

    @staticmethod
    def _count_images(directory: Path) -> int:
        if not directory.is_dir():
            return 0
        return sum(
            1
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        )

    def _build_colmap_command(self, command: str, args: list[str]) -> list[str]:
        binary = self._resolve_colmap_binary()
        if binary is None:
            raise _ColmapExecutionError(
                f"COLMAP binary is not available: {self._settings.colmap_binary!r}",
                error_code="COLMAP_UNAVAILABLE",
            )

        full_command = [str(binary), command, *args]
        if command in {"feature_extractor", "exhaustive_matcher"}:
            gpu_flag = "1" if self._settings.colmap_use_gpu else "0"
            if command == "feature_extractor":
                full_command.extend(["--FeatureExtraction.use_gpu", gpu_flag])
            elif command == "exhaustive_matcher":
                full_command.extend(["--FeatureMatching.use_gpu", gpu_flag])
        return full_command

    def _run_colmap(
        self,
        command: str,
        args: list[str],
        *,
        emit: Callable[[str, str], None],
        check: ControlCallback,
    ) -> list[str]:
        full_command = self._build_colmap_command(command, args)
        logger.info("Running COLMAP | command=%s", " ".join(full_command))

        try:
            process = subprocess.Popen(
                full_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except OSError as exc:
            raise _ColmapExecutionError(
                f"Failed to start COLMAP {command}: {exc}",
                error_code=_error_code_for_command(command),
            ) from exc

        output_lines: list[str] = []
        return_code = 1

        try:
            assert process.stdout is not None
            for line in process.stdout:
                stripped = line.rstrip("\n")
                if stripped:
                    clean = strip_ansi(stripped)
                    output_lines.append(clean)
                    emit(clean)
                check()
            return_code = process.wait()
        except Exception:
            # Includes PipelineControlError (pause/cancel from check()): stop COLMAP, re-raise.
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            raise

        if return_code != 0:
            error_code = _error_code_for_command(command)
            tail = strip_ansi(
                "\n".join(output_lines[-20:]) if output_lines else "Unknown COLMAP error"
            )
            raise _ColmapExecutionError(
                f"COLMAP {command} failed (exit {return_code}): {tail}",
                error_code=error_code,
            )

        return output_lines

    def _find_best_sparse_model(
        self,
        *,
        sparse_dir: Path,
        text_model_dir: Path,
        emit: Callable[[str, str], None],
        check: ControlCallback,
    ) -> tuple[Path | None, int]:
        """Select the sparse model with the most registered images."""
        if not sparse_dir.is_dir():
            return None, 0

        candidates = sorted(path for path in sparse_dir.iterdir() if path.is_dir())
        best_model: Path | None = None
        best_count = 0

        for candidate in candidates:
            if not sparse_model_has_files(candidate):
                emit(f"Skipping sparse model {candidate.name}: no COLMAP model files.", level="warn")
                continue

            try:
                images_txt, _ = self._ensure_model_text_files(
                    sparse_model=candidate,
                    text_output_dir=text_model_dir / f"eval_{candidate.name}",
                    emit=emit,
                    check=check,
                )
            except _ColmapExecutionError as exc:
                emit(f"Skipping sparse model {candidate.name}: {exc}", level="warn")
                continue
            count = registered_image_count(images_txt)
            emit(f"Sparse model {candidate.name}: {count} registered image(s).")
            if not sparse_model_is_usable(candidate, registered_images=count):
                continue
            if count > best_count:
                best_count = count
                best_model = candidate

        return best_model, best_count

    def _resolve_model_text_files(
        self,
        *,
        sparse_model: Path,
        text_model_dir: Path,
        emit: Callable[[str, str], None],
        check: ControlCallback,
    ) -> tuple[Path, Path]:
        images_txt, cameras_txt = self._ensure_model_text_files(
            sparse_model=sparse_model,
            text_output_dir=text_model_dir,
            emit=emit,
            check=check,
        )
        return cameras_txt, images_txt

    def _ensure_model_text_files(
        self,
        *,
        sparse_model: Path,
        text_output_dir: Path,
        emit: Callable[[str, str], None],
        check: ControlCallback,
    ) -> tuple[Path, Path]:
        cameras_txt = sparse_model / "cameras.txt"
        images_txt = sparse_model / "images.txt"
        if cameras_txt.is_file() and images_txt.is_file():
            return images_txt, cameras_txt

        if text_output_dir.exists():
            shutil.rmtree(text_output_dir)
        text_output_dir.mkdir(parents=True, exist_ok=True)
        self._run_colmap(
            "model_converter",
            [
                "--input_path",
                str(sparse_model),
                "--output_path",
                str(text_output_dir),
                "--output_type",
                "TXT",
            ],
            emit=emit,
            check=check,
        )

        cameras_txt = text_output_dir / "cameras.txt"
        images_txt = text_output_dir / "images.txt"
        if not cameras_txt.is_file() or not images_txt.is_file():
            raise _ColmapExecutionError(
                "COLMAP model_converter did not produce cameras.txt and images.txt.",
                error_code="TRANSFORM_EXPORT_FAILED",
            )
        return images_txt, cameras_txt


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
