"""Mesh cleanup engine abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

from app.models.job import Job

LogCallback = Callable[[str, str], None] | Callable[[str], None]
ProgressCallback = Callable[[int], None]
ControlCallback = Callable[[], None]


@dataclass
class MeshCleanupResult:
    """Structured result from a mesh cleanup run."""

    success: bool
    message: str
    error_code: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


class MeshCleanupEngine(ABC):
    """Interface for turning a Stage 5 mesh into validated, cleaned exports."""

    name: str

    @abstractmethod
    def validate(self, job: Job) -> MeshCleanupResult:
        """Verify that a job has a Stage 5 mesh that can be cleaned."""

    @abstractmethod
    def clean(
        self,
        job: Job,
        *,
        log: LogCallback | None = None,
        on_progress: ProgressCallback | None = None,
        check_control: ControlCallback | None = None,
    ) -> MeshCleanupResult:
        """Write cleaned PLY/OBJ/GLB next to (never over) the source mesh."""
