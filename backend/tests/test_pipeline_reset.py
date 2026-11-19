"""Tests for resetting pipeline stages, clearing stale errors, and concurrency guards."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.core.config import Settings
from app.jobs.pipeline_repository import PipelineRepository
from app.jobs.repository import JobRepository
from app.models.job import Job
from app.pipeline.constants import PIPELINE_STAGE_DEFINITIONS
from app.pipeline.pipeline_manager import PipelineBusyError, PipelineManager
from app.pipeline.pipeline_state import PipelineState
from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.pipeline.stage_registry import StageRegistry

JOB_ID = "job_000201"
OTHER_JOB_ID = "job_000202"


class _FakeStage(PipelineStage):
    def __init__(self, stage_id: int, state: PipelineState) -> None:
        self._stage_id = stage_id
        self._state = state
        self.seen_last_error: list[object] = []

    @property
    def stage_id(self) -> int:
        return self._stage_id

    def name(self) -> str:
        return PIPELINE_STAGE_DEFINITIONS[self._stage_id - 1][1]

    def status(self, job: Job) -> str:
        return self._state.stage_status(job.id, self._stage_id)

    async def run(self, job: Job, ctx: StageContext) -> StageResult:
        document = self._state.load(job.id)
        self.seen_last_error.append(document["execution"]["last_error"])
        return StageResult(success=True, message="ok")

    async def rollback(self, job: Job, ctx: StageContext) -> StageResult:
        return StageResult(success=True, message="ok")


@pytest.fixture
def env(tmp_path: Path):
    settings = Settings(JOBS_ROOT=str(tmp_path / "jobs"))
    repository = JobRepository(settings=settings)
    state = PipelineState(PipelineRepository(settings))
    stages = [_FakeStage(stage_id, state) for stage_id, _ in PIPELINE_STAGE_DEFINITIONS]
    manager = PipelineManager(
        registry=StageRegistry(stages=stages),
        state=state,
        repository=repository,
    )

    for job_id in (JOB_ID, OTHER_JOB_ID):
        repository.create_folder_structure(job_id)
        repository.save(Job(id=job_id, name=job_id, engine="Instant-NGP", image_count=2))
        state.save(
            job_id,
            {
                "execution": {
                    "status": "idle",
                    "current_stage_id": None,
                    "paused_at": None,
                    "cancelled_at": None,
                    "last_error": "Traceback: No module named 'commentjson'",
                },
                "stages": [
                    {
                        "id": stage_id,
                        "name": name,
                        "status": "completed" if stage_id <= 5 else "waiting",
                        "progress": 100 if stage_id <= 5 else 0,
                        "completed_at": "2026-09-19T00:00:00+00:00" if stage_id <= 5 else None,
                    }
                    for stage_id, name in PIPELINE_STAGE_DEFINITIONS
                ],
            },
        )

    job_root = repository.jobs_root / JOB_ID
    artifacts = {
        "upload": job_root / "uploaded_images" / "r_0.png",
        "masked": job_root / "masked_images" / "r_0.png",
        "transforms": job_root / "camera" / "transforms" / "transforms.json",
        "snapshot": job_root / "instant_ngp" / "snapshot.msgpack",
        "mesh_glb": job_root / "meshes" / "2026-09-19T044936_224775_0000" / "mesh.glb",
        "mesh_obj": job_root / "meshes" / "2026-09-19T044936_224775_0000" / "mesh.obj",
    }
    for path in artifacts.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"data")

    return manager, state, repository, artifacts, stages


def _statuses(document: dict) -> dict[int, str]:
    return {stage["id"]: stage["status"] for stage in document["stages"]}


def test_reset_from_stage_3_preserves_earlier_stages_and_files(env) -> None:
    manager, state, repository, artifacts, _ = env
    other_before = state.repository.pipeline_path(OTHER_JOB_ID).read_bytes()

    document = asyncio.run(manager.reset_from_stage(JOB_ID, 3))

    assert _statuses(document) == {
        1: "completed",
        2: "completed",
        3: "waiting",
        4: "waiting",
        5: "waiting",
        6: "waiting",
        7: "waiting",
    }
    for stage in document["stages"]:
        if stage["id"] >= 3:
            assert stage["progress"] == 0
            assert stage["completed_at"] is None
        else:
            assert stage["completed_at"] == "2026-09-19T00:00:00+00:00"
    assert document["execution"]["last_error"] is None
    assert document["execution"]["status"] == "idle"

    for path in artifacts.values():
        assert path.read_bytes() == b"data", path
    assert state.repository.pipeline_path(OTHER_JOB_ID).read_bytes() == other_before


def test_reconcile_does_not_recomplete_reset_stages_from_stale_artifacts(env) -> None:
    manager, state, _, artifacts, _ = env
    asyncio.run(manager.reset_from_stage(JOB_ID, 3))
    assert artifacts["transforms"].is_file() and artifacts["snapshot"].is_file()

    document = state.reconcile_with_job(
        JOB_ID,
        image_count=2,
        uploaded_at=None,
        masked_image_count=1,
        has_transforms=True,
        has_snapshot=True,
    )

    assert _statuses(document)[3] == "waiting"
    assert _statuses(document)[4] == "waiting"


def test_reset_rejects_upload_and_unknown_stages(env) -> None:
    manager = env[0]
    with pytest.raises(ValueError):
        asyncio.run(manager.reset_from_stage(JOB_ID, 1))
    with pytest.raises(ValueError):
        asyncio.run(manager.reset_from_stage(JOB_ID, 99))


def test_reset_and_run_are_rejected_while_job_is_busy(env) -> None:
    manager, state, repository, _, _ = env
    # A second manager mimics a separate API request.
    other_request = PipelineManager(registry=manager._registry, state=state, repository=repository)

    async def scenario() -> None:
        async with manager._job_lock(JOB_ID):
            with pytest.raises(PipelineBusyError):
                await other_request.reset_from_stage(JOB_ID, 3)
            with pytest.raises(PipelineBusyError):
                await other_request.run_stage(JOB_ID, 6)
            with pytest.raises(PipelineBusyError):
                await other_request.run_pipeline(JOB_ID)

    asyncio.run(scenario())
    assert _statuses(state.load(JOB_ID))[3] == "completed"


def test_new_run_clears_stale_last_error(env) -> None:
    manager, state, _, _, stages = env
    asyncio.run(manager.reset_from_stage(JOB_ID, 3))
    state.mark_stage_failed(JOB_ID, 3, message="old COLMAP failure")
    assert state.load(JOB_ID)["execution"]["last_error"] == "old COLMAP failure"

    result = asyncio.run(manager.run_stage(JOB_ID, 3))

    assert result.stopped_reason == "completed"
    assert stages[2].seen_last_error == [None]
    document = state.load(JOB_ID)
    assert document["execution"]["last_error"] is None
    assert _statuses(document)[3] == "completed"
    assert _statuses(document)[4] == "waiting"


def test_reset_then_pipeline_reruns_dependent_stages_in_order(env) -> None:
    manager, state, _, _, _ = env
    asyncio.run(manager.reset_from_stage(JOB_ID, 3))

    result = asyncio.run(manager.run_pipeline(JOB_ID))

    assert result.stages_run == [3, 4, 5, 6, 7]
    assert all(status == "completed" for status in _statuses(state.load(JOB_ID)).values())
