"""Camera estimation engine abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

from app.models.job import Job

LogCallback = Callable[[str, str], None] | Callable[[str], None]
ProgressCallback = Callable[[int], None]
ControlCallback = Callable[[], None]


@dataclass
class CameraEstimationResult:
    """Structured result from a camera estimation run."""

    success: bool
    message: str
    error_code: str | None = None
    transforms_path: str | None = None
    registered_images: int = 0
    data: dict[str, Any] = field(default_factory=dict)


class CameraEstimationEngine(ABC):
    """Interface for structure-from-motion camera estimation engines."""

    name: str

    @abstractmethod
    def validate(self, job: Job) -> CameraEstimationResult:
        """Verify that a job is ready for camera estimation."""

    @abstractmethod
    def estimate(
        self,
        job: Job,
        *,
        log: LogCallback | None = None,
        on_progress: ProgressCallback | None = None,
        check_control: ControlCallback | None = None,
    ) -> CameraEstimationResult:
        """Estimate camera poses and write ``transforms.json``."""
