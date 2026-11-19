"""Regression tests: job-level status/progress must follow the persisted pipeline stages.

Jobs completed all seven stages yet were reported as "waiting" at 0%, because nothing
updated the job-level fields in ``metadata.json`` that the job list returned.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.core.config import Settings
from app.jobs.lifecycle import derive_lifecycle, pipeline_duration_seconds
from app.jobs.pipeline_repository import PipelineRepository
from app.jobs.repository import JobRepository
from app.models.job import Job
from app.pipeline.constants import PIPELINE_STAGE_DEFINITIONS
from app.pipeline.pipeline_manager import PipelineManager
from app.pipeline.pipeline_state import PipelineState
from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.pipeline.stage_registry import StageRegistry
from app.services.dashboard_stats import build_dashboard_summary
from app.services.job_summary import build_job_summary

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


def _document(*statuses: str, execution: str = "idle", progress: dict[int, int] | None = None):
    progress = progress or {}
    return {
        "execution": {"status": execution, "current_stage_id": None},
        "stages": [
            {
                "id": stage_id,
                "name": name,
                "status": status,
                "progress": 100 if status == "completed" else progress.get(stage_id, 0),
                "completed_at": (
                    (NOW - timedelta(days=1, minutes=10 - stage_id)).isoformat()
                    if status == "completed"
                    else None
                ),
            }
            for (stage_id, name), status in zip(PIPELINE_STAGE_DEFINITIONS, statuses)
        ],
    }


ALL_DONE = ("completed",) * 7
WAITING = ("waiting",) * 7


# --- derive_lifecycle ---------------------------------------------------------------


def test_all_stages_completed_is_completed_at_100() -> None:
    lifecycle = derive_lifecycle(_document(*ALL_DONE))
    assert lifecycle.status == "completed"
    assert lifecycle.progress == 100
    assert lifecycle.completed_at == (NOW - timedelta(days=1, minutes=3)).isoformat()


def test_untouched_pipeline_stays_waiting_at_0() -> None:
    lifecycle = derive_lifecycle(_document(*WAITING))
    assert (lifecycle.status, lifecycle.progress) == ("waiting", 0)


def test_running_progress_comes_from_stage_progress() -> None:
    document = _document(
        "completed", "completed", "completed", "running", "waiting", "waiting", "waiting",
        execution="running",
        progress={4: 50},
    )
    lifecycle = derive_lifecycle(document)
    assert lifecycle.status == "running"
    assert lifecycle.progress == round((300 + 50) / 7)


def test_failed_stage_is_failed_and_keeps_progress_reached() -> None:
    lifecycle = derive_lifecycle(
        _document("completed", "completed", "failed", "waiting", "waiting", "waiting", "waiting")
    )
    assert lifecycle.status == "failed"
    assert lifecycle.progress == round(200 / 7)
    assert lifecycle.completed_at is None


def test_cancelled_run_is_cancelled_not_completed() -> None:
    lifecycle = derive_lifecycle(
        _document(*("completed",) * 6, "waiting", execution="cancelled")
    )
    assert lifecycle.status == "cancelled"
    assert lifecycle.progress < 100


def test_missing_pipeline_falls_back_to_stored_fields() -> None:
    assert derive_lifecycle(None, fallback_status="queued").status == "queued"


def test_pipeline_duration_needs_stage_start_times() -> None:
    assert pipeline_duration_seconds(_document(*ALL_DONE)) is None
    document = _document(*ALL_DONE)
    for stage in document["stages"]:
        finished = datetime.fromisoformat(stage["completed_at"])
        stage["started_at"] = (finished - timedelta(seconds=10)).isoformat()
    assert pipeline_duration_seconds(document) == pytest.approx(70.0)


# --- read-time summaries for existing jobs ---------------------------------------------


@pytest.fixture
def workspace(tmp_path: Path):
    settings = Settings(JOBS_ROOT=str(tmp_path / "jobs"), OUTPUTS_ROOT=str(tmp_path / "outputs"))
    return settings, JobRepository(settings=settings), PipelineRepository(settings)


def _add_job(workspace, job_id: str, document: dict | None, **fields) -> Job:
    _settings, repository, pipelines = workspace
    repository.create_folder_structure(job_id)
    job = Job(id=job_id, name=job_id, engine="Instant-NGP", **fields)
    repository.save(job)
    if document is not None:
        pipelines.save(job_id, document)
    return job


def test_legacy_completed_job_reports_completed_without_writing(workspace) -> None:
    """Old jobs keep status "waiting"/0 in metadata.json; the API must still report completed."""
    _settings, repository, pipelines = workspace
    _add_job(
        workspace,
        "job_000301",
        _document(*ALL_DONE),
        reconstruction_started_at="2026-10-15T08:42:18+00:00",
        reconstruction_completed_at="2026-10-15T09:03:28+00:00",
    )
    root = repository.jobs_root / "job_000301"
    before = {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()}

    summary = build_job_summary(repository.get("job_000301"), repository.jobs_root, pipelines)

    assert summary["status"] == "completed"
    assert summary["progress"] == 100
    assert summary["training_duration_seconds"] == 1270
    assert [stage["status"] for stage in summary["stages"]] == list(ALL_DONE)
    after = {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()}
    assert after == before, "summaries must not modify job records"


def test_job_without_pipeline_file_is_not_given_one(workspace) -> None:
    _settings, repository, pipelines = workspace
    _add_job(workspace, "job_000302", None, status="queued")
    summary = build_job_summary(repository.get("job_000302"), repository.jobs_root, pipelines)
    assert summary["status"] == "queued"
    assert not pipelines.pipeline_path("job_000302").exists()


def test_running_marker_left_by_a_restart_is_not_active(workspace) -> None:
    _settings, repository, pipelines = workspace
    _add_job(
        workspace,
        "job_000303",
        _document("completed", "completed", "running", *("waiting",) * 4, execution="running"),
    )
    summary = build_job_summary(repository.get("job_000303"), repository.jobs_root, pipelines)
    assert summary["interrupted"] is True
    assert summary["status"] == "waiting"


# --- persistence by the pipeline manager -------------------------------------------------


class _OkStage(PipelineStage):
    def __init__(self, stage_id: int, fail: bool = False) -> None:
        self._stage_id = stage_id
        self._fail = fail

    @property
    def stage_id(self) -> int:
        return self._stage_id

    def name(self) -> str:
        return PIPELINE_STAGE_DEFINITIONS[self._stage_id - 1][1]

    def status(self, job: Job) -> str:
        return "waiting"

    async def run(self, job: Job, ctx: StageContext) -> StageResult:
        if self._fail:
            return StageResult(success=False, message="boom")
        return StageResult(success=True, message="ok")

    async def rollback(self, job: Job, ctx: StageContext) -> StageResult:
        return StageResult(success=True, message="ok")


def _manager(workspace, *, fail_stage: int | None = None) -> PipelineManager:
    settings, repository, pipelines = workspace
    stages = [
        _OkStage(stage_id, fail=stage_id == fail_stage) for stage_id, _ in PIPELINE_STAGE_DEFINITIONS
    ]
    return PipelineManager(
        registry=StageRegistry(stages=stages),
        state=PipelineState(pipelines),
        repository=repository,
    )


def test_completed_run_persists_status_and_survives_restart(workspace) -> None:
    settings, repository, _pipelines = workspace
    _add_job(workspace, "job_000304", _document(*WAITING), image_count=3)

    result = asyncio.run(_manager(workspace).run_pipeline("job_000304"))
    assert result.stopped_reason == "completed"

    # A fresh process: new repository objects reading only what is on disk.
    metadata = json.loads((repository.jobs_root / "job_000304" / "metadata.json").read_text())
    assert metadata["status"] == "completed"
    assert metadata["progress"] == 100
    assert metadata["started_at"] is not None
    assert metadata["completed_at"] is not None

    fresh_repository = JobRepository(settings=settings)
    summary = build_job_summary(
        fresh_repository.get("job_000304"), fresh_repository.jobs_root, PipelineRepository(settings)
    )
    assert (summary["status"], summary["progress"]) == ("completed", 100)
    assert summary["pipeline_duration_seconds"] is not None


def test_failed_run_persists_failed_not_completed(workspace) -> None:
    _settings, repository, _pipelines = workspace
    _add_job(workspace, "job_000305", _document(*WAITING), image_count=3)

    asyncio.run(_manager(workspace, fail_stage=3).run_pipeline("job_000305"))

    job = repository.get("job_000305")
    assert job.status == "failed"
    assert job.progress == round(200 / 7)
    assert job.completed_at is None


# --- dashboard summary ---------------------------------------------------------------


def _metrics(**overrides):
    return {
        "final_loss": 0.0003,
        "mean_steps_per_second": 27.6,
        "checkpoint_count": 1,
        "peak_vram_mib": None,
        "source": "pipeline",
        **overrides,
    }


def test_dashboard_counts_and_medians(workspace) -> None:
    settings, _repository, _pipelines = workspace
    _add_job(
        workspace,
        "job_000310",
        _document(*ALL_DONE),
        reconstruction_started_at="2026-11-17T10:00:00+00:00",
        reconstruction_completed_at="2026-11-17T10:20:00+00:00",
        training_metrics=_metrics(peak_vram_mib=1500),
    )
    # Completed more than seven days ago, with an invalid VRAM value that must be skipped.
    old = _document(*ALL_DONE)
    for stage in old["stages"]:
        stage["completed_at"] = "2026-10-15T15:57:10+00:00"
    _add_job(
        workspace,
        "job_000311",
        old,
        reconstruction_started_at="2026-10-15T08:00:00+00:00",
        reconstruction_completed_at="2026-10-15T08:40:00+00:00",
        training_metrics=_metrics(peak_vram_mib=0),
    )
    _add_job(workspace, "job_000312", _document(*WAITING))
    _add_job(
        workspace,
        "job_000313",
        _document("completed", "running", *("waiting",) * 5, execution="running"),
    )
    _add_job(
        workspace,
        "job_000314",
        _document("completed", "failed", *("waiting",) * 5),
        training_metrics=_metrics(peak_vram_mib=3900),
    )

    PipelineManager._locks["job_000313"] = asyncio.Lock()
    asyncio.run(PipelineManager._locks["job_000313"].acquire())
    try:
        summary = build_dashboard_summary(settings, now=NOW)
    finally:
        PipelineManager._locks.pop("job_000313", None)

    jobs = summary["jobs"]
    assert jobs["total"] == 5
    assert jobs["active"] == 1, "only the running job is active; completed ones are not"
    assert jobs["completed_total"] == 2
    assert jobs["completed_7d"] == 1
    assert jobs["failed"] == 1

    engine = summary["engines"]["Instant-NGP"]
    assert engine["completed_jobs"] == 2
    assert engine["median_training_seconds"]["value"] == pytest.approx(1800)
    assert engine["median_training_seconds"]["sample_size"] == 2
    # Only completed jobs with a valid (positive) peak count; the failed job's 3900 is excluded.
    assert engine["median_peak_vram_mib"]["value"] == 1500
    assert engine["median_peak_vram_mib"]["sample_size"] == 1
    assert engine["median_psnr_db"]["value"] is None
    assert engine["median_psnr_db"]["sample_size"] == 0
    assert engine["median_psnr_db"]["unavailable_reason"]


def test_experiment_records_do_not_enter_production_statistics(workspace) -> None:
    settings, _repository, _pipelines = workspace
    record = settings.outputs_path / "experiments" / "group" / "E9_test"
    record.mkdir(parents=True)
    (record / "metrics.json").write_text(
        json.dumps(
            {
                "experiment": "E9_test",
                "status": "completed",
                "training": {"seconds": 1000, "gpu_used_mib_peak": 1200},
                "psnr": {"E9": {"psnr_mean": 35.0, "frames_evaluated": 25}},
            }
        )
    )

    summary = build_dashboard_summary(settings, now=NOW)

    assert summary["experimental"][0]["psnr_mean_db"] == 35.0
    assert summary["experimental"][0]["peak_vram_mib"] == 1200
    assert summary["jobs"]["total"] == 0
    assert summary["training"]["value"] is None
    assert summary["engines"] == {}


# --- API responses (route functions called with test-scoped dependencies) ---------------


def _api_job(workspace, job_id: str):
    from app.api.jobs import get_job, list_jobs
    from app.services.job_manager import JobManagerImpl

    _settings, repository, _pipelines = workspace
    manager = JobManagerImpl(repository=repository)
    single = asyncio.run(get_job(job_id, manager=manager))
    listed = asyncio.run(list_jobs(manager=manager))
    return single, {job.id: job for job in listed.jobs}


def test_api_reports_completed_running_waiting_and_failed(workspace) -> None:
    _add_job(workspace, "job_000320", _document(*ALL_DONE))
    _add_job(workspace, "job_000321", _document(*WAITING))
    failed = _document("completed", "completed", "failed", *("waiting",) * 4)
    failed["execution"]["last_error"] = "COLMAP registered 3 of 40 images"
    _add_job(workspace, "job_000322", failed)
    _add_job(
        workspace,
        "job_000323",
        _document("completed", "completed", "completed", "running", *("waiting",) * 3,
                  execution="running", progress={4: 40}),
    )

    PipelineManager._locks["job_000323"] = asyncio.Lock()
    asyncio.run(PipelineManager._locks["job_000323"].acquire())
    try:
        completed, listed = _api_job(workspace, "job_000320")
    finally:
        PipelineManager._locks.pop("job_000323", None)

    assert (completed.status, completed.progress) == ("completed", 100)
    assert completed.last_error is None
    assert len(completed.stages) == 7
    assert (listed["job_000321"].status, listed["job_000321"].progress) == ("waiting", 0)
    assert listed["job_000322"].status == "failed"
    assert listed["job_000322"].failed_stage == {"id": 3, "name": "Camera Estimation"}
    assert listed["job_000322"].last_error == "COLMAP registered 3 of 40 images"
    assert listed["job_000323"].status == "running"
    assert listed["job_000323"].progress == round((300 + 40) / 7)


def test_api_status_survives_restart_without_stale_metadata(workspace) -> None:
    """metadata.json may still say waiting/0 (legacy); the API must report the pipeline state."""
    settings, _repository, _pipelines = workspace
    _add_job(workspace, "job_000324", _document(*ALL_DONE), status="waiting", progress=0)

    # Fresh objects, as after a backend restart.
    fresh = (settings, JobRepository(settings=settings), PipelineRepository(settings))
    job, _listed = _api_job(fresh, "job_000324")
    assert (job.status, job.progress) == ("completed", 100)
