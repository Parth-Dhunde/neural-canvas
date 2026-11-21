"""Pause and cancel reach the run that is executing, and interrupted stages can run again."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.engines.instant_ngp.launcher import InstantNGPLauncher
from app.jobs.job_logs import JobLogStore
from app.jobs.lifecycle import derive_lifecycle
from app.jobs.pipeline_repository import PipelineRepository
from app.jobs.repository import JobRepository
from app.models.job import Job
from app.pipeline.constants import PIPELINE_STAGE_DEFINITIONS
from app.pipeline.pipeline_manager import (
    PipelineControlError,
    PipelineManager,
    PipelineNotRunningError,
)
from app.pipeline.pipeline_state import PipelineState
from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.pipeline.stage_registry import StageRegistry

JOB_ID = "job_000301"


class _Stage(PipelineStage):
    def __init__(self, stage_id: int, state: PipelineState, slow: bool = False) -> None:
        self._stage_id = stage_id
        self._state = state
        self._slow = slow
        self.started = asyncio.Event() if slow else None

    @property
    def stage_id(self) -> int:
        return self._stage_id

    def name(self) -> str:
        return PIPELINE_STAGE_DEFINITIONS[self._stage_id - 1][1]

    def status(self, job: Job) -> str:
        return self._state.stage_status(job.id, self._stage_id)

    async def run(self, job: Job, ctx: StageContext) -> StageResult:
        if self._slow:
            assert self.started is not None
            self.started.set()
            for _ in range(500):
                ctx.check_control()
                await asyncio.sleep(0.01)
        return StageResult(success=True, message="ok")

    async def rollback(self, job: Job, ctx: StageContext) -> StageResult:
        return StageResult(success=True, message="ok")


def _managers(tmp_path: Path, slow_stage: int = 3):
    settings = Settings(JOBS_ROOT=str(tmp_path / "jobs"))
    repository = JobRepository(settings=settings)
    state = PipelineState(PipelineRepository(settings))
    stages = [_Stage(i, state, slow=(i == slow_stage)) for i, _ in PIPELINE_STAGE_DEFINITIONS]
    log_store = JobLogStore(repository.jobs_root)

    def build() -> PipelineManager:
        return PipelineManager(
            registry=StageRegistry(stages=stages),
            state=state,
            repository=repository,
            log_store=log_store,
        )

    repository.create_folder_structure(JOB_ID)
    repository.save(Job(id=JOB_ID, name=JOB_ID, engine="Instant-NGP"))
    build().initialize(JOB_ID)
    state.mark_upload_complete(JOB_ID)
    return build, state, stages[slow_stage - 1]


@pytest.mark.parametrize("action", ["cancel", "pause"])
def test_control_from_another_request_stops_the_run(tmp_path: Path, action: str) -> None:
    build, state, slow = _managers(tmp_path)

    async def scenario():
        runner = build()
        task = asyncio.create_task(runner.run_pipeline(JOB_ID))
        await asyncio.wait_for(slow.started.wait(), timeout=5)
        getattr(build(), action)(JOB_ID)  # a different manager instance, like a new request
        return await asyncio.wait_for(task, timeout=5)

    result = asyncio.run(scenario())
    expected = "cancelled" if action == "cancel" else "paused"
    assert result.stopped_reason == expected
    document = state.load(JOB_ID)
    stages = {s["id"]: s["status"] for s in document["stages"]}
    assert stages[3] == "waiting"  # interrupted stage can run again
    assert stages[2] == "completed" and stages[4] == "waiting"
    assert document["execution"]["status"] == expected
    assert derive_lifecycle(document).status == expected
    assert not PipelineManager.is_running(JOB_ID)


def test_run_continues_after_pause_without_restart_error(tmp_path: Path) -> None:
    build, state, slow = _managers(tmp_path)

    async def scenario():
        task = asyncio.create_task(build().run_pipeline(JOB_ID))
        await asyncio.wait_for(slow.started.wait(), timeout=5)
        build().pause(JOB_ID)
        await task
        slow._slow = False
        return await build().run_pipeline(JOB_ID)

    result = asyncio.run(scenario())
    assert result.stopped_reason == "completed"
    document = state.load(JOB_ID)
    assert all(s["status"] == "completed" for s in document["stages"])
    assert document["execution"]["last_error"] is None


@pytest.mark.parametrize("action", ["cancel", "pause"])
def test_control_without_a_run_is_refused(tmp_path: Path, action: str) -> None:
    build, state, _ = _managers(tmp_path)
    before = state.load(JOB_ID)["execution"]["status"]
    with pytest.raises(PipelineNotRunningError):
        getattr(build(), action)(JOB_ID)
    assert state.load(JOB_ID)["execution"]["status"] == before


def test_launcher_terminates_training_process_when_stopped(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "ngp"
    (root / "scripts").mkdir(parents=True)
    pid_file = tmp_path / "pid"
    (root / "scripts" / "run.py").write_text(
        "import os, sys, time\n"
        f"open({str(pid_file)!r}, 'w').write(str(os.getpid()))\n"
        "while True:\n"
        "    print('step', flush=True)\n"
        "    time.sleep(0.05)\n",
        encoding="utf-8",
    )
    launcher = InstantNGPLauncher(Settings(INSTANT_NGP_ROOT=str(root)))
    monkeypatch.setattr(launcher, "validate_runtime", lambda: SimpleNamespace(ready=True))
    monkeypatch.setattr(launcher, "_resolve_interpreter", lambda: sys.executable)

    lines = 0

    def check() -> None:
        nonlocal lines
        lines += 1
        if lines >= 3:
            raise PipelineControlError("cancelled")

    with pytest.raises(PipelineControlError):
        launcher._run([], job_id="job_000302", check_control=check)

    pid = int(pid_file.read_text())
    deadline = time.monotonic() + 5
    alive = True
    while time.monotonic() < deadline:
        try:
            with open(f"/proc/{pid}/stat", encoding="utf-8") as handle:
                state = handle.read().split()[2]
            alive = state != "Z"
        except FileNotFoundError:
            alive = False
        if not alive:
            break
        time.sleep(0.05)
    assert not alive, "training process kept running after the run was stopped"
    assert launcher.active_pid("job_000302") is None
