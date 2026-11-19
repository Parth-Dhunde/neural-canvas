"""Tests for Instant-NGP training metrics parsing, backfill and GPU memory sampling."""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.engines.instant_ngp.training_metrics import (
    TrainingMetricsTracker,
    count_checkpoints,
    parse_tqdm_elapsed,
    parse_training_log,
)
from app.jobs.pipeline_repository import PipelineRepository
from app.jobs.repository import JobRepository
from app.models.job import Job
from app.services.gpu_memory import PeakGpuMemorySampler
from app.services.job_summary import build_job_summary

ESC = "\x1b"
LOG = (
    f"{ESC}[0m14:12:19 {ESC}[0;32mSUCCESS  {ESC}[0mInitialized CUDA\n"
    "Training:   0%|          | 0/35000 [00:00<?, ?steps/s]\r"
    "Training:   0%|          | 1/35000 [00:00<00:06, 5178.15steps/s, loss=0.0381]\r"
    "Training:  50%|#####     | 17500/35000 [10:30<10:30, 27.80steps/s, loss=0.0012]\r"
    "Training: 100%|#########9| 34998/35000 [21:07<00:00, 27.60steps/s, loss=0.00029]\n"
    "14:33:28 SUCCESS  Saved snapshot '/x/snapshot.msgpack'\n"
)


def test_tracker_reads_final_bar_values() -> None:
    tracker = TrainingMetricsTracker()
    for line in LOG.replace("\r", "\n").splitlines():
        tracker.observe(line)

    data = tracker.to_dict()
    assert data["final_loss"] == 0.00029
    assert data["last_logged_step"] == 34998
    assert data["total_steps"] == 35000
    assert data["tqdm_elapsed_seconds"] == 21 * 60 + 7
    assert data["mean_steps_per_second"] == round(34998 / 1267, 3)
    assert data["last_steps_per_second"] == 27.6
    assert data["snapshots_saved"] == 1


def test_tracker_handles_slow_rate_units_and_hours() -> None:
    tracker = TrainingMetricsTracker()
    tracker.observe("Training:  1%| | 10/1000 [1:00:05<9:00:00, 2.00s/steps, loss=0.5]")
    assert tracker.elapsed_seconds == 3605
    assert tracker.last_steps_per_second == 0.5
    assert parse_tqdm_elapsed("bad") is None


def test_log_without_progress_reports_nothing(tmp_path: Path) -> None:
    log = tmp_path / "training.log"
    log.write_text("crashed before training\n")
    assert parse_training_log(log) is None


def test_backfill_from_training_log_is_labelled_and_has_no_vram(tmp_path: Path) -> None:
    settings = Settings(JOBS_ROOT=str(tmp_path / "jobs"))
    repository = JobRepository(settings=settings)
    pipelines = PipelineRepository(settings)
    repository.create_folder_structure("job_000401")
    repository.save(Job(id="job_000401", name="j", engine="Instant-NGP"))
    pipelines.save(
        "job_000401",
        {
            "execution": {"status": "idle"},
            "stages": [
                {"id": i, "status": "completed" if i <= 4 else "waiting", "progress": 0}
                for i in range(1, 8)
            ],
        },
    )
    ngp = repository.jobs_root / "job_000401" / "instant_ngp"
    ngp.mkdir(exist_ok=True)
    (ngp / "training.log").write_text(LOG)
    (ngp / "snapshot.msgpack").write_bytes(b"x")
    log_bytes = (ngp / "training.log").read_bytes()

    metrics = build_job_summary(repository.get("job_000401"), repository.jobs_root, pipelines)[
        "training_metrics"
    ]

    assert metrics["source"] == "training_log"
    assert metrics["final_loss"] == 0.00029
    assert metrics["checkpoint_count"] == 1
    assert metrics["peak_vram_mib"] is None
    assert (ngp / "training.log").read_bytes() == log_bytes


def test_recorded_metrics_take_precedence_over_backfill(tmp_path: Path) -> None:
    settings = Settings(JOBS_ROOT=str(tmp_path / "jobs"))
    repository = JobRepository(settings=settings)
    repository.create_folder_structure("job_000402")
    repository.save(
        Job(
            id="job_000402",
            name="j",
            engine="Instant-NGP",
            training_metrics={"final_loss": 0.1, "peak_vram_mib": 1400, "source": "pipeline"},
        )
    )
    summary = build_job_summary(
        repository.get("job_000402"), repository.jobs_root, PipelineRepository(settings)
    )
    assert summary["training_metrics"]["peak_vram_mib"] == 1400


def test_count_checkpoints(tmp_path: Path) -> None:
    assert count_checkpoints(tmp_path / "missing") == 0
    (tmp_path / "checkpoints").mkdir()
    (tmp_path / "snapshot.msgpack").write_bytes(b"")
    (tmp_path / "checkpoints" / "step_1000.msgpack").write_bytes(b"")
    (tmp_path / "training.log").write_text("")
    assert count_checkpoints(tmp_path) == 2


def test_gpu_sampler_tracks_peak_for_the_process_only() -> None:
    readings = iter([{10: 900, 99: 3000}, {10: 1400}, {10: 1200}, None])
    sampler = PeakGpuMemorySampler(lambda: 10, query=lambda: next(readings))
    for _ in range(4):
        sampler.sample_once()
    assert sampler.peak_mib == 1400
    assert sampler.samples == 3


def test_gpu_sampler_without_data_reports_unavailable() -> None:
    sampler = PeakGpuMemorySampler(lambda: None, query=lambda: {1: 100})
    sampler.sample_once()
    assert sampler.peak_mib is None
