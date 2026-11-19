"""Instant-NGP reconstruction engine."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from app.core.config import Settings, get_settings
from app.engines.instant_ngp.launcher import InstantNGPLauncher
from app.engines.instant_ngp.training_metrics import TrainingMetricsTracker, count_checkpoints
from app.engines.instant_ngp.validation import validate_instant_ngp
from app.engines.reconstruction.base import (
    ControlCallback,
    LogCallback,
    ProgressCallback,
    ReconstructionEngine,
    ReconstructionResult,
)
from app.jobs.repository import JobRepository
from app.jobs.structure import (
    SUPPORTED_IMAGE_EXTENSIONS,
    camera_transforms_file,
    camera_transforms_path,
    instant_ngp_checkpoints_path,
    instant_ngp_output_path,
    instant_ngp_snapshot_path,
    instant_ngp_snapshot_relative_path,
    instant_ngp_training_log_path,
    masked_images_path,
)
from app.models.job import Job
from app.services.gpu_memory import PeakGpuMemorySampler

MIN_MASKED_IMAGES = 2

# tqdm progress bar, e.g. "Training:  42%|####| 14700/35000 [10:02<13:51, 24.4steps/s, loss=0.016]".
_TQDM_RE = re.compile(r"(\d+)/(\d+) \[[^\]]*\]")
_LOSS_RE = re.compile(r"loss=([0-9.eE+-]+)")
PROGRESS_LOG_INTERVAL_PERCENT = 5
TRAINING_PROGRESS_START = 20
TRAINING_PROGRESS_END = 95


class TrainingOutputForwarder:
    """Forward Instant-NGP output to the pipeline log, condensing tqdm progress updates.

    tqdm redraws its bar with carriage returns, which arrive as one line per update; only
    every ``PROGRESS_LOG_INTERVAL_PERCENT`` is logged, while stage progress tracks steps.
    """

    def __init__(
        self,
        *,
        emit: Callable[..., None],
        progress: ProgressCallback,
        metrics: TrainingMetricsTracker | None = None,
    ) -> None:
        self._emit = emit
        self._progress = progress
        self._metrics = metrics
        self._last_logged_percent = -1
        self._last_progress = TRAINING_PROGRESS_START
        self._plain_lines = 0
        self._saw_steps = False

    def __call__(self, line: str) -> None:
        if self._metrics is not None:
            self._metrics.observe(line)
        match = _TQDM_RE.search(line)
        if match is None:
            self._plain_lines += 1
            if not self._saw_steps and self._plain_lines % 25 == 0:
                self._set_progress(TRAINING_PROGRESS_START + self._plain_lines // 25)
            self._emit(line)
            return

        self._saw_steps = True
        step, total = int(match.group(1)), int(match.group(2))
        if total > 0:
            percent = min(100, step * 100 // total)
            span = TRAINING_PROGRESS_END - TRAINING_PROGRESS_START
            self._set_progress(TRAINING_PROGRESS_START + percent * span // 100)
            bucket = percent - percent % PROGRESS_LOG_INTERVAL_PERCENT
            if bucket > self._last_logged_percent:
                self._last_logged_percent = bucket
                loss = _LOSS_RE.search(line)
                suffix = f", loss={loss.group(1)}" if loss else ""
                self._emit(f"Training {percent}% ({step}/{total} steps{suffix})")

        # Log lines printed while the bar is drawn share its line (no newline in between).
        trailing = line[match.end():].strip()
        if trailing:
            self._emit(trailing)

    def _set_progress(self, value: int) -> None:
        value = min(TRAINING_PROGRESS_END, value)
        if value > self._last_progress:
            self._last_progress = value
            self._progress(value)


class InstantNGPReconstructionEngine(ReconstructionEngine):
    """Run NVIDIA Instant-NGP via ``InstantNGPLauncher``."""

    name = "instant-ngp"

    def __init__(
        self,
        settings: Settings | None = None,
        repository: JobRepository | None = None,
        launcher: InstantNGPLauncher | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._repository = repository or JobRepository()
        self._launcher = launcher or InstantNGPLauncher(self._settings)

    def validate(self, job: Job) -> ReconstructionResult:
        engine_error = self._validate_engine()
        if engine_error is not None:
            return engine_error

        transforms = camera_transforms_file(self._repository.jobs_root, job.id)
        if not transforms.is_file():
            return ReconstructionResult(
                success=False,
                message=(
                    "Camera transforms are missing. Complete camera estimation before "
                    "starting reconstruction."
                ),
                error_code="VALIDATION_FAILED",
            )

        image_count = self._count_masked_images(job.id)
        if image_count < MIN_MASKED_IMAGES:
            return ReconstructionResult(
                success=False,
                message=(
                    f"At least {MIN_MASKED_IMAGES} masked images are required for "
                    f"reconstruction. Found {image_count}."
                ),
                error_code="VALIDATION_FAILED",
            )

        return ReconstructionResult(
            success=True,
            message="Validation passed.",
            data={"masked_image_count": image_count},
        )

    def run(
        self,
        job: Job,
        *,
        log: LogCallback | None = None,
        on_progress: ProgressCallback | None = None,
        check_control: ControlCallback | None = None,
    ) -> ReconstructionResult:
        validation = self.validate(job)
        if not validation.success:
            return validation

        emit = _make_logger(log)
        progress = on_progress or (lambda _value: None)
        check = check_control or (lambda: None)

        jobs_root = self._repository.jobs_root
        output_dir = instant_ngp_output_path(jobs_root, job.id)
        snapshot_path = instant_ngp_snapshot_path(jobs_root, job.id)
        training_log_path = instant_ngp_training_log_path(jobs_root, job.id)
        checkpoints_dir = instant_ngp_checkpoints_path(jobs_root, job.id)
        scene_dir = camera_transforms_path(jobs_root, job.id)

        output_dir.mkdir(parents=True, exist_ok=True)
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        if snapshot_path.exists():
            snapshot_path.unlink()

        emit("Loading transforms...")
        progress(10)
        check()

        emit("Training...")
        progress(20)

        metrics = TrainingMetricsTracker()
        on_line = TrainingOutputForwarder(emit=emit, progress=progress, metrics=metrics)
        sampler = PeakGpuMemorySampler(lambda: self._launcher.active_pid(job.id))
        sampler.start()

        try:
            return_code = self._launcher.run_training(
                job_id=job.id,
                scene_dir=scene_dir,
                snapshot_path=snapshot_path,
                log_path=training_log_path,
                on_line=on_line,
                check_control=check,
            )
        except RuntimeError as exc:
            emit(str(exc), level="error")
            return ReconstructionResult(
                success=False,
                message=str(exc),
                error_code=_error_code_from_message(str(exc)),
            )
        finally:
            peak_vram_mib = sampler.stop()

        if return_code != 0:
            message = _read_tail(training_log_path) or f"Instant-NGP exited with code {return_code}"
            emit(message, level="error")
            return ReconstructionResult(
                success=False,
                message=message,
                error_code="TRAINING_FAILED",
            )

        if not snapshot_path.is_file():
            return ReconstructionResult(
                success=False,
                message="Instant-NGP finished without producing snapshot.msgpack.",
                error_code="SNAPSHOT_MISSING",
            )

        emit("Saving snapshot...")
        progress(98)

        relative_snapshot = instant_ngp_snapshot_relative_path()
        return ReconstructionResult(
            success=True,
            message="Training completed.",
            snapshot_path=relative_snapshot,
            data={
                "snapshot_path": relative_snapshot,
                "training_log_path": str(training_log_path.relative_to(output_dir.parent)),
                "checkpoints_dir": checkpoints_dir.name,
                "scene_dir": str(scene_dir.relative_to(output_dir.parent)),
                "training_metrics": {
                    **metrics.to_dict(),
                    "checkpoint_count": count_checkpoints(output_dir),
                    "peak_vram_mib": peak_vram_mib,
                    "vram_samples": sampler.samples,
                    "source": "pipeline",
                },
            },
        )

    def cancel(self, job: Job) -> ReconstructionResult:
        if not self._launcher.cancel(job.id):
            return ReconstructionResult(
                success=False,
                message="No active Instant-NGP process for this job.",
                error_code="NOT_RUNNING",
            )
        return ReconstructionResult(success=True, message="Instant-NGP training cancelled.")

    def _validate_engine(self) -> ReconstructionResult | None:
        result = validate_instant_ngp(self._settings)
        if result.ready:
            return None
        return ReconstructionResult(
            success=False,
            message=result.message or "Instant-NGP is not ready.",
            error_code=result.error_code or "INSTANT_NGP_UNAVAILABLE",
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


def _make_logger(log: LogCallback | None) -> Callable[[str, str], None]:
    def emit(message: str, level: str = "info") -> None:
        if log is None:
            return
        try:
            log(message, level)
        except TypeError:
            log(message)

    return emit


def _read_tail(path: Path, *, max_lines: int = 20) -> str:
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return ""
    return "\n".join(lines[-max_lines:])


def _error_code_from_message(message: str) -> str:
    if "Python version mismatch" in message:
        return "PYTHON_VERSION_MISMATCH"
    return "INSTANT_NGP_UNAVAILABLE"
