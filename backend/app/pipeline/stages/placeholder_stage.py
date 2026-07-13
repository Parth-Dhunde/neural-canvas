"""Placeholder stages for pipeline steps not yet implemented."""

from __future__ import annotations

from app.models.job import Job
from app.pipeline.stage import PipelineStage, StageContext, StageResult


class PlaceholderStage(PipelineStage):
    """Stage that reports ``Not Implemented`` without side effects."""

    def __init__(self, stage_id: int, stage_name: str) -> None:
        self._stage_id = stage_id
        self._stage_name = stage_name

    @property
    def stage_id(self) -> int:
        return self._stage_id

    @property
    def is_implemented(self) -> bool:
        return False

    def name(self) -> str:
        return self._stage_name

    def status(self, job: Job) -> str:
        return "waiting"

    async def run(self, job: Job, ctx: StageContext) -> StageResult:
        ctx.log(f"{self._stage_name}: Not Implemented", level="warn")
        return StageResult(
            success=False,
            message="Not Implemented",
            implemented=False,
        )

    async def rollback(self, job: Job, ctx: StageContext) -> StageResult:
        return StageResult(
            success=False,
            message="Not Implemented",
            implemented=False,
        )
