"""Ordered registry of reconstruction pipeline stages."""

from __future__ import annotations

from app.pipeline.constants import PIPELINE_STAGE_DEFINITIONS
from app.pipeline.stage import PipelineStage


class StageRegistry:
    """Provides the ordered list of pipeline stages."""

    def __init__(self, stages: list[PipelineStage] | None = None) -> None:
        self._stages = stages if stages is not None else self._build_default_stages()

    def _build_default_stages(self) -> list[PipelineStage]:
        from app.pipeline.stages.background_removal_stage import BackgroundRemovalStage
        from app.pipeline.stages.camera_estimation_stage import CameraEstimationStage
        from app.pipeline.stages.export_stage import ExportStage
        from app.pipeline.stages.mesh_cleanup_stage import MeshCleanupStage
        from app.pipeline.stages.mesh_generation_stage import MeshGenerationStage
        from app.pipeline.stages.reconstruction_stage import ReconstructionStage
        from app.pipeline.stages.upload_stage import UploadStage

        upload = UploadStage()
        background_removal = BackgroundRemovalStage()
        camera_estimation = CameraEstimationStage()
        reconstruction = ReconstructionStage()
        mesh_generation = MeshGenerationStage()
        return [
            upload,
            background_removal,
            camera_estimation,
            reconstruction,
            mesh_generation,
            MeshCleanupStage(),
            ExportStage(),
        ]

    def all(self) -> list[PipelineStage]:
        return list(self._stages)

    def implemented(self) -> list[PipelineStage]:
        return [stage for stage in self._stages if stage.is_implemented]

    def get(self, stage_id: int) -> PipelineStage | None:
        for stage in self._stages:
            if stage.stage_id == stage_id:
                return stage
        return None

    def create_initial_stages(self) -> list[dict[str, object]]:
        return [
            {
                "id": stage_id,
                "name": stage_name,
                "status": "waiting",
                "progress": 0,
                "completed_at": None,
            }
            for stage_id, stage_name in PIPELINE_STAGE_DEFINITIONS
        ]
