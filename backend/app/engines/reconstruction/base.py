"""Reconstruction engine abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

from app.models.job import Job

LogCallback = Callable[[str, str], None] | Callable[[str], None]
ProgressCallback = Callable[[int], None]
ControlCallback = Callable[[], None]


@dataclass
class ReconstructionResult:
    """Structured result from a reconstruction run."""

    success: bool
    message: str
    error_code: str | None = None
    snapshot_path: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


class ReconstructionEngine(ABC):
    """Interface for neural reconstruction engines."""

    name: str

    @abstractmethod
    def validate(self, job: Job) -> ReconstructionResult:
        """Verify that a job is ready for reconstruction."""

    @abstractmethod
    def run(
        self,
        job: Job,
        *,
        log: LogCallback | None = None,
        on_progress: ProgressCallback | None = None,
        check_control: ControlCallback | None = None,
    ) -> ReconstructionResult:
        """Run reconstruction and write engine outputs for the job."""

    @abstractmethod
    def cancel(self, job: Job) -> ReconstructionResult:
        """Request cancellation of an in-flight reconstruction."""
