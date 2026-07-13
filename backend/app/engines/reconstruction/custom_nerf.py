"""Custom NeRF reconstruction engine placeholder."""

from __future__ import annotations

from app.engines.reconstruction.base import (
    ControlCallback,
    LogCallback,
    ProgressCallback,
    ReconstructionEngine,
    ReconstructionResult,
)
from app.models.job import Job


class CustomNeRFReconstructionEngine(ReconstructionEngine):
    """Placeholder for the future Custom NeRF engine."""

    name = "custom-nerf"

    def validate(self, job: Job) -> ReconstructionResult:
        return ReconstructionResult(
            success=False,
            message="Custom NeRF is not implemented.",
            error_code="NOT_IMPLEMENTED",
        )

    def run(
        self,
        job: Job,
        *,
        log: LogCallback | None = None,
        on_progress: ProgressCallback | None = None,
        check_control: ControlCallback | None = None,
    ) -> ReconstructionResult:
        if log is not None:
            try:
                log("Custom NeRF is not implemented.", "warn")
            except TypeError:
                log("Custom NeRF is not implemented.")
        return ReconstructionResult(
            success=False,
            message="Custom NeRF is not implemented.",
            error_code="NOT_IMPLEMENTED",
        )

    def cancel(self, job: Job) -> ReconstructionResult:
        return ReconstructionResult(
            success=False,
            message="Custom NeRF is not implemented.",
            error_code="NOT_IMPLEMENTED",
        )
