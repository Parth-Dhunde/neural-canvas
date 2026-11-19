"""Tests for per-job pipeline log storage, incremental retrieval, and log forwarding."""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.text import infer_log_level, strip_ansi
from app.engines.reconstruction.instant_ngp import TrainingOutputForwarder
from app.jobs.job_logs import JobLogStore, get_job_log_store
from app.jobs.pipeline_repository import PipelineRepository
from app.jobs.repository import JobRepository
from app.models.job import Job
from app.pipeline.constants import PIPELINE_STAGE_DEFINITIONS
from app.pipeline.pipeline_manager import PipelineManager
from app.pipeline.pipeline_state import PipelineState
from app.pipeline.stage import PipelineStage, StageContext, StageResult
from app.pipeline.stage_registry import StageRegistry
from app.services.job_manager import JobManagerImpl

JOB_A = "job_000301"
JOB_B = "job_000302"


@pytest.fixture
def jobs_root(tmp_path: Path) -> Path:
    root = tmp_path / "jobs"
    for job_id in (JOB_A, JOB_B):
        (root / job_id / "logs").mkdir(parents=True)
    return root


def _messages(entries) -> list[str]:
    return [entry.message for entry in entries]


def test_incremental_reads_return_only_new_entries(jobs_root: Path) -> None:
    store = JobLogStore(jobs_root)
    for index in range(5):
        store.append(JOB_A, f"line {index}")

    first = store.read(JOB_A, after=0)
    assert [entry.seq for entry in first.entries] == [1, 2, 3, 4, 5]
    assert first.next_after == 5 and first.last_seq == 5 and not first.has_more

    store.append(JOB_A, "line 5")
    store.append(JOB_A, "line 6")
    second = store.read(JOB_A, after=first.next_after)
    assert _messages(second.entries) == ["line 5", "line 6"]
    assert second.next_after == 7

    idle = store.read(JOB_A, after=second.next_after)
    assert idle.entries == [] and idle.next_after == 7


def test_limit_pages_and_tail(jobs_root: Path) -> None:
    store = JobLogStore(jobs_root)
    for index in range(10):
        store.append(JOB_A, f"line {index}")

    page = store.read(JOB_A, after=0, limit=4)
    assert [entry.seq for entry in page.entries] == [1, 2, 3, 4]
    assert page.has_more is True and page.next_after == 4

    tail = store.read(JOB_A, tail=3)
    assert [entry.seq for entry in tail.entries] == [8, 9, 10]
    assert tail.next_after == 10 and tail.truncated is True


def test_jobs_are_isolated(jobs_root: Path) -> None:
    store = JobLogStore(jobs_root)
    store.append(JOB_A, "a1")
    store.append(JOB_B, "b1")
    store.append(JOB_A, "a2")

    assert _messages(store.read(JOB_A).entries) == ["a1", "a2"]
    assert _messages(store.read(JOB_B).entries) == ["b1"]
    assert store.read(JOB_B).last_seq == 1

    persisted_b = (jobs_root / JOB_B / "logs" / "pipeline.jsonl").read_text(encoding="utf-8")
    assert "a1" not in persisted_b and "b1" in persisted_b


def test_memory_buffer_is_bounded_but_disk_keeps_history(jobs_root: Path) -> None:
    store = JobLogStore(jobs_root, max_entries=10)
    for index in range(25):
        store.append(JOB_A, f"line {index}")

    page = store.read(JOB_A, after=0, limit=1000)
    assert [entry.seq for entry in page.entries] == list(range(16, 26))
    assert page.truncated is True

    lines = (jobs_root / JOB_A / "logs" / "pipeline.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 25


def test_buffered_job_count_is_bounded(jobs_root: Path) -> None:
    store = JobLogStore(jobs_root, max_jobs=2)
    for index in range(5):
        store.append(f"job_{index:06d}", "x")
    assert len(store._buffers) == 2


def test_history_and_sequence_survive_restart(jobs_root: Path) -> None:
    JobLogStore(jobs_root).append(JOB_A, "before restart")
    JobLogStore(jobs_root).append(JOB_A, "second")  # fresh store restores from disk

    restarted = JobLogStore(jobs_root)
    page = restarted.read(JOB_A)
    assert _messages(page.entries) == ["before restart", "second"]
    assert restarted.append(JOB_A, "after").seq == 3


def test_cursor_ahead_of_log_resets(jobs_root: Path) -> None:
    store = JobLogStore(jobs_root)
    store.append(JOB_A, "only")
    page = store.read(JOB_A, after=50)
    assert page.reset is True
    assert _messages(page.entries) == ["only"]


def test_entries_strip_ansi_and_normalize_level(jobs_root: Path) -> None:
    store = JobLogStore(jobs_root)
    entry = store.append(JOB_A, "\x1b[0;34mPROGRESS \x1b[0mhello\x1b[K", level="warning")
    assert entry.message == "PROGRESS hello"
    assert entry.level == "warn"
    assert store.append(JOB_A, "x", level="nonsense").level == "info"


def test_log_file_rotates_when_large(jobs_root: Path) -> None:
    store = JobLogStore(jobs_root, max_file_bytes=200)
    for index in range(20):
        store.append(JOB_A, f"line {index} " + "x" * 20)
    log_dir = jobs_root / JOB_A / "logs"
    assert (log_dir / "pipeline.jsonl.1").is_file()
    assert (log_dir / "pipeline.jsonl").stat().st_size < 400


def test_unknown_job_workspace_is_not_created(jobs_root: Path) -> None:
    store = JobLogStore(jobs_root)
    store.append("job_999999", "memory only")
    assert not (jobs_root / "job_999999").exists()
    assert _messages(store.read("job_999999").entries) == ["memory only"]


def test_concurrent_appends_keep_unique_ordered_sequences(jobs_root: Path) -> None:
    store = JobLogStore(jobs_root)

    def worker(name: str) -> None:
        for index in range(200):
            store.append(JOB_A, f"{name}-{index}")

    threads = [threading.Thread(target=worker, args=(f"t{n}",)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    seqs = [entry.seq for entry in store.read(JOB_A, limit=1000).entries]
    assert seqs == list(range(1, 801))
    persisted = (jobs_root / JOB_A / "logs" / "pipeline.jsonl").read_text(encoding="utf-8")
    assert sorted(json.loads(line)["seq"] for line in persisted.splitlines()) == seqs


@pytest.mark.parametrize(
    ("line", "level"),
    [
        ("E20261015 13:45:27.238 model.cc:441] Failed to read", "error"),
        ("W20261015 13:45:27.238 sift.cc:10] low features", "warn"),
        ("09:59:23 ERROR    CUDA out of memory", "error"),
        ("09:59:23 WARNING  something odd", "warn"),
        ("09:59:23 SUCCESS  Initialized CUDA", "ok"),
        ("Traceback (most recent call last):", "error"),
        ("ModuleNotFoundError: No module named 'commentjson'", "error"),
        ("I20261015 13:45:27.238 model.cc:441] Cameras: 1", "info"),
        ("Extracting features...", "info"),
        # Real Instant-NGP output colors its severity tag.
        ("15:17:39 \x1b[0;33mWARNING \x1b[0m Stand-in warning\x1b[K", "warn"),
        ("15:17:49 \x1b[0;32mSUCCESS \x1b[0m Saved snapshot\x1b[K", "ok"),
        ("15:17:49 \x1b[0;31mERROR   \x1b[0m CUDA out of memory\x1b[K", "error"),
        ("15:17:49 \x1b[0;34mINFO    \x1b[0m Loading NeRF dataset\x1b[K", "info"),
    ],
)
def test_infer_log_level(line: str, level: str) -> None:
    assert infer_log_level(line) == level


def test_strip_ansi_removes_erase_sequences() -> None:
    assert strip_ansi("\x1b[0;32mSUCCESS \x1b[0mdone\x1b[K") == "SUCCESS done"


def test_training_output_condenses_tqdm_and_tracks_progress() -> None:
    logs: list[str] = []
    progress: list[int] = []
    forward = TrainingOutputForwarder(
        emit=lambda message, level="info": logs.append(message), progress=progress.append
    )

    forward("09:59:23 INFO     Loading NeRF dataset from")
    forward("Training:   0%|          | 0/35000 [00:00<?, ?steps/s]09:59:23 INFO     Loading network")
    for step in range(1, 35001, 350):
        forward(f"Training:  {step * 100 // 35000}%|##| {step}/35000 [00:10<00:01, 25steps/s, loss=0.0158]")
    forward("Training: 100%|##| 35000/35000 [20:02<00:00, 29.10steps/s, loss=0.0150]")

    training = [line for line in logs if line.startswith("Training ")]
    assert training[0] == "Training 0% (0/35000 steps)"
    assert training[-1] == "Training 100% (35000/35000 steps, loss=0.0150)"
    assert len(training) == 21  # one line per 5% instead of one per tqdm redraw
    assert "09:59:23 INFO     Loading network" in logs
    assert "09:59:23 INFO     Loading NeRF dataset from" in logs
    assert progress == sorted(progress) and progress[-1] == 95


class _LoggingStage(PipelineStage):
    def __init__(self, stage_id: int, state: PipelineState, lines: list[str]) -> None:
        self._stage_id = stage_id
        self._state = state
        self._lines = lines

    @property
    def stage_id(self) -> int:
        return self._stage_id

    def name(self) -> str:
        return PIPELINE_STAGE_DEFINITIONS[self._stage_id - 1][1]

    def status(self, job: Job) -> str:
        return self._state.stage_status(job.id, self._stage_id)

    async def run(self, job: Job, ctx: StageContext) -> StageResult:
        for line in self._lines:
            ctx.log(line)
        return StageResult(success=True, message="ok")

    async def rollback(self, job: Job, ctx: StageContext) -> StageResult:
        return StageResult(success=True, message="ok")


def _manager(tmp_path: Path, lines: list[str]) -> tuple[PipelineManager, JobRepository, JobLogStore]:
    settings = Settings(JOBS_ROOT=str(tmp_path / "jobs"))
    repository = JobRepository(settings=settings)
    state = PipelineState(PipelineRepository(settings))
    # Same process-wide store the API endpoint uses (keyed by the tmp jobs root).
    store = get_job_log_store(repository.jobs_root)
    stages = [_LoggingStage(stage_id, state, lines) for stage_id, _ in PIPELINE_STAGE_DEFINITIONS]
    manager = PipelineManager(
        registry=StageRegistry(stages=stages), state=state, repository=repository, log_store=store
    )
    for job_id in (JOB_A, JOB_B):
        repository.create_folder_structure(job_id)
        repository.save(Job(id=job_id, name=job_id, engine="Instant-NGP", image_count=1))
        manager.initialize(job_id)
    return manager, repository, store


def test_stage_logs_are_stored_with_stage_id_and_level(tmp_path: Path) -> None:
    manager, _, store = _manager(
        tmp_path,
        [
            "Extracting features...",
            "E20261015 13:45:27 x.cc:1] boom",
            "15:17:39 \x1b[0;33mWARNING \x1b[0m colored warning\x1b[K",
        ],
    )
    asyncio.run(manager.run_stage(JOB_A, 1))

    entries = store.read(JOB_A).entries
    by_message = {entry.message: entry for entry in entries}
    assert by_message["Extracting features..."].stage_id == 1
    assert by_message["E20261015 13:45:27 x.cc:1] boom"].level == "error"
    # Stored without color codes and with the severity from the colored tag.
    assert by_message["15:17:39 WARNING  colored warning"].level == "warn"
    assert by_message["Stage 1 (Upload) starting."].stage_id == 1
    assert by_message["Stage 1 (Upload) completed."].level == "ok"
    assert store.read(JOB_B).entries == []


def test_run_result_logs_are_scoped_to_the_run_but_history_is_kept(tmp_path: Path) -> None:
    manager, _, store = _manager(tmp_path, ["work"])
    asyncio.run(manager.run_stage(JOB_A, 1))
    first_total = store.last_seq(JOB_A)

    result = asyncio.run(manager.run_stage(JOB_A, 2))

    assert result.logs and all(line.startswith(f"[{JOB_A}] ") for line in result.logs)
    assert "[job_000301] Stage 1 (Upload) completed." not in result.logs
    assert "[job_000301] Stage 2 (Background Removal) completed." in result.logs
    assert store.last_seq(JOB_A) > first_total
    assert store.read(JOB_A, after=0, limit=1000).entries[0].seq == 1


def test_logs_api_returns_incremental_pages(tmp_path: Path) -> None:
    from app.api.jobs import get_job_logs, get_job_pipeline

    manager, repository, _ = _manager(tmp_path, ["hello"])
    asyncio.run(manager.run_stage(JOB_A, 1))
    job_manager = JobManagerImpl(repository)

    first = asyncio.run(get_job_logs(JOB_A, after=0, limit=500, tail=None, manager=job_manager))
    assert first.job_id == JOB_A
    assert "hello" in [entry.message for entry in first.entries]
    assert first.next_after == first.last_seq

    manager.log(JOB_A, "later line", stage_id=2)
    second = asyncio.run(
        get_job_logs(JOB_A, after=first.next_after, limit=500, tail=None, manager=job_manager)
    )
    assert [(e.message, e.stage_id) for e in second.entries] == [("later line", 2)]

    other = asyncio.run(get_job_logs(JOB_B, after=0, limit=500, tail=None, manager=job_manager))
    assert other.entries == []

    pipeline = asyncio.run(
        get_job_pipeline(JOB_A, manager=job_manager, pipeline_manager=manager)
    )
    assert pipeline.execution is not None and pipeline.execution.status == "idle"
    assert pipeline.stages[0].status == "completed"


def test_logs_api_rejects_unknown_job(tmp_path: Path) -> None:
    from fastapi import HTTPException

    from app.api.jobs import get_job_logs

    _, repository, _ = _manager(tmp_path, [])
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            get_job_logs(
                "job_999999", after=0, limit=500, tail=None, manager=JobManagerImpl(repository)
            )
        )
    assert excinfo.value.status_code == 404


def test_polling_pipeline_state_does_not_rewrite_unchanged_file(tmp_path: Path) -> None:
    manager, repository, _ = _manager(tmp_path, [])
    asyncio.run(manager.run_stage(JOB_A, 1))
    path = PipelineRepository(Settings(JOBS_ROOT=str(repository.jobs_root))).pipeline_path(JOB_A)
    before = (path.read_bytes(), path.stat().st_mtime_ns)

    for _ in range(3):
        manager.reconcile_with_job(
            JOB_A, image_count=1, uploaded_at=None, masked_image_count=0
        )

    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
    assert not list(path.parent.glob(".pipeline.json.*.tmp"))
