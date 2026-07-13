"""Mesh generation engine abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

from app.models.job import Job

LogCallback = Callable[[str, str], None] | Callable[[str], None]
ProgressCallback = Callable[[int], None]
ControlCallback = Callable[[], None]


@dataclass
class MeshGenerationResult:
    """Structured result from a mesh generation run."""

    success: bool
    message: str
    error_code: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


class MeshGenerationEngine(ABC):
    """Interface for converting reconstruction artifacts into meshes."""

    name: str

    @abstractmethod
    def validate(self, job: Job) -> MeshGenerationResult:
        """Verify that a job is ready for mesh generation."""

    @abstractmethod
    def generate(
        self,
        job: Job,
        *,
        log: LogCallback | None = None,
        on_progress: ProgressCallback | None = None,
        check_control: ControlCallback | None = None,
    ) -> MeshGenerationResult:
        """Generate mesh outputs for the job."""

    @abstractmethod
    def cancel(self, job: Job) -> MeshGenerationResult:
        """Request cancellation of an in-flight mesh generation run."""
