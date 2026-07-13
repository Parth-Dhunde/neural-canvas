"""Pipeline stage contracts and execution context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.models.job import Job


@dataclass
class StageResult:
    """Outcome of a single stage execution."""

    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    implemented: bool = True


class StageContext(Protocol):
    """Callbacks provided to stages during execution."""

    @property
    def job_id(self) -> str:
        """Active job identifier."""

    def log(self, message: str, level: str = "info") -> None:
        """Emit a log line through the pipeline manager."""

    def update_progress(self, progress: int) -> None:
        """Persist in-stage progress to ``pipeline.json``."""

    def check_control(self) -> None:
        """Raise if the pipeline has been paused or cancelled."""


class PipelineStage(ABC):
    """Strategy interface for a single reconstruction pipeline stage."""

    @property
    @abstractmethod
    def stage_id(self) -> int:
        """Numeric stage identifier (1-based)."""

    @abstractmethod
    def name(self) -> str:
        """Human-readable stage name."""

    @property
    def is_implemented(self) -> bool:
        """Return ``True`` when the stage has a real implementation."""
        return True

    @abstractmethod
    async def run(self, job: Job, ctx: StageContext) -> StageResult:
        """Execute this stage for ``job``."""

    @abstractmethod
    async def rollback(self, job: Job, ctx: StageContext) -> StageResult:
        """Undo stage side effects where possible."""

    @abstractmethod
    def status(self, job: Job) -> str:
        """Return the persisted status string for this stage."""
