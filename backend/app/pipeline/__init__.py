"""Centralized reconstruction pipeline orchestration."""

from importlib import import_module
from typing import Any

# Resolved lazily (PEP 562): importing a submodule such as ``app.pipeline.constants`` must not
# load the pipeline manager, whose imports lead back to ``app.jobs.pipeline_repository``.
_EXPORTS = {
    "PipelineManager": "app.pipeline.pipeline_manager",
    "get_pipeline_manager": "app.pipeline.pipeline_manager",
    "PipelineStage": "app.pipeline.stage",
    "StageContext": "app.pipeline.stage",
    "StageResult": "app.pipeline.stage",
    "StageRegistry": "app.pipeline.stage_registry",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(_EXPORTS[name]), name)
