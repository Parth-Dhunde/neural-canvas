"""Job deletion: removes only the job's own directory, refuses running/protected/unsafe jobs."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.jobs import bulk_delete_jobs, delete_job
from app.core.config import Settings
from app.jobs.deletion import TRASH_PREFIX, JobDeletionError, purge_deletion_leftovers
from app.jobs.job_logs import get_job_log_store
from app.jobs.repository import JobRepository
from app.models.job import Job
from app.pipeline.pipeline_manager import PipelineManager
from app.schemas.job import JobBulkDeleteRequest
from app.services.job_deletion import JobDeletionService


def _make_job(repository: JobRepository, job_id: str, status: str = "waiting") -> Path:
    root = repository.create_folder_structure(job_id)
    repository.save(Job(id=job_id, name=job_id, engine="Instant-NGP", status=status))
    (root / "uploaded_images" / "a.jpg").write_bytes(b"\xff\xd8 image")
    (root / "meshes" / "run").mkdir(parents=True)
    (root / "meshes" / "run" / "mesh.glb").write_bytes(b"glTF....")
    return root


@pytest.fixture
def env(tmp_path: Path):
    settings = Settings(JOBS_ROOT=str(tmp_path / "jobs"), PROTECTED_JOB_IDS="job_000099")
    repository = JobRepository(settings=settings)
    repository.ensure_jobs_root()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("must survive", encoding="utf-8")
    return repository, JobDeletionService(repository), outside


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("status", ["waiting", "completed", "failed"])
def test_deletes_job_directory_and_nothing_else(env, status: str) -> None:
    repository, service, outside = env
    target = _make_job(repository, "job_000001", status)
    sibling = _make_job(repository, "job_000002")

    _run(service.delete("job_000001"))

    assert not target.exists()
    assert sibling.is_dir() and repository.get("job_000002") is not None
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "must survive"
    assert [job.id for job in repository.list_all()] == ["job_000002"]
    assert not any(p.name.startswith(TRASH_PREFIX) for p in repository.jobs_root.iterdir())


def test_repeated_delete_reports_not_found_without_side_effects(env) -> None:
    repository, service, _ = env
    _make_job(repository, "job_000001")
    keep = _make_job(repository, "job_000002")
    _run(service.delete("job_000001"))

    with pytest.raises(JobDeletionError) as info:
        _run(service.delete("job_000001"))
    assert info.value.code == "not_found"
    assert keep.is_dir()


def test_running_job_is_refused_and_untouched(env) -> None:
    repository, service, _ = env
    root = _make_job(repository, "job_000003")

    async def scenario() -> str:
        lock = PipelineManager.job_lock("job_000003")
        async with lock:
            try:
                await service.delete("job_000003")
            except JobDeletionError as exc:
                return exc.code
        return "deleted"

    assert _run(scenario()) == "running"
    assert (root / "metadata.json").is_file()
    assert (root / "uploaded_images" / "a.jpg").is_file()


@pytest.mark.parametrize(
    "job_id",
    ["../outside", "job_1", "job_000001/../job_000002", "", "job_0000001", "JOB_000001", "job_00000a"],
)
def test_invalid_identifiers_are_rejected(env, job_id: str) -> None:
    repository, service, outside = env
    _make_job(repository, "job_000001")
    with pytest.raises(JobDeletionError) as info:
        _run(service.delete(job_id))
    assert info.value.code == "invalid"
    assert repository.get("job_000001") is not None
    assert (outside / "keep.txt").exists()


def test_symlinked_job_directory_is_refused(env) -> None:
    repository, service, outside = env
    (outside / "metadata.json").write_text(
        json.dumps({"id": "job_000004", "name": "x", "engine": "Instant-NGP"}), encoding="utf-8"
    )
    link = repository.jobs_root / "job_000004"
    link.symlink_to(outside, target_is_directory=True)

    with pytest.raises(JobDeletionError) as info:
        _run(service.delete("job_000004"))
    assert info.value.code == "unsafe"
    assert link.is_symlink()
    assert (outside / "keep.txt").exists() and (outside / "metadata.json").exists()


def test_symlinks_inside_job_are_removed_not_followed(env) -> None:
    repository, service, outside = env
    root = _make_job(repository, "job_000005")
    (root / "exports" / "to_outside_dir").symlink_to(outside, target_is_directory=True)
    (root / "exports" / "to_outside_file").symlink_to(outside / "keep.txt")

    _run(service.delete("job_000005"))

    assert not root.exists()
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "must survive"


def test_protected_job_is_refused(env) -> None:
    repository, service, _ = env
    root = _make_job(repository, "job_000099")
    with pytest.raises(JobDeletionError) as info:
        _run(service.delete("job_000099"))
    assert info.value.code == "protected"
    assert root.is_dir()


def test_directory_without_metadata_is_not_deleted(env) -> None:
    repository, service, _ = env
    partial = repository.jobs_root / "job_000006"
    partial.mkdir()
    (partial / "uploaded_images").mkdir()
    with pytest.raises(JobDeletionError) as info:
        _run(service.delete("job_000006"))
    assert info.value.code == "not_found"
    assert partial.is_dir()


def test_partially_completed_job_is_deleted(env) -> None:
    repository, service, _ = env
    root = repository.create_folder_structure("job_000007")
    repository.save(Job(id="job_000007", name="half", engine="Instant-NGP"))
    (root / "pipeline.json").write_text("{not valid json", encoding="utf-8")
    _run(service.delete("job_000007"))
    assert not root.exists()


def test_log_buffer_is_dropped(env) -> None:
    repository, service, _ = env
    _make_job(repository, "job_000008")
    store = get_job_log_store(repository.jobs_root)
    store.append("job_000008", "hello")
    assert store.last_seq("job_000008") == 1
    _run(service.delete("job_000008"))
    assert store.last_seq("job_000008") == 0


def test_interrupted_deletion_leftovers_are_purged_but_symlinks_are_not_followed(env) -> None:
    repository, service, outside = env
    leftover = repository.jobs_root / f"{TRASH_PREFIX}job_000010-abc"
    (leftover / "meshes").mkdir(parents=True)
    (leftover / "meshes" / "mesh.ply").write_bytes(b"ply")
    trap = repository.jobs_root / f"{TRASH_PREFIX}job_000011-def"
    trap.symlink_to(outside, target_is_directory=True)

    assert purge_deletion_leftovers(repository.jobs_root) == 1
    assert not leftover.exists()
    assert trap.is_symlink() and (outside / "keep.txt").exists()


def test_bulk_delete_reports_each_job(env) -> None:
    repository, service, _ = env
    _make_job(repository, "job_000001", "completed")
    _make_job(repository, "job_000002", "failed")
    _make_job(repository, "job_000099")

    outcomes = _run(
        service.delete_many(
            ["job_000001", "job_000002", "job_000001", "job_000050", "job_000099", "../x"]
        )
    )
    by_id = {o.job_id: o.status for o in outcomes}
    assert by_id == {
        "job_000001": "deleted",
        "job_000002": "deleted",
        "job_000050": "not_found",
        "job_000099": "refused",
        "../x": "refused",
    }
    assert [job.id for job in repository.list_all()] == ["job_000099"]


def test_bulk_delete_skips_running_job(env) -> None:
    repository, service, _ = env
    _make_job(repository, "job_000001")
    running = _make_job(repository, "job_000002")

    async def scenario():
        async with PipelineManager.job_lock("job_000002"):
            return await service.delete_many(["job_000001", "job_000002"])

    by_id = {o.job_id: o for o in _run(scenario())}
    assert by_id["job_000001"].status == "deleted"
    assert by_id["job_000002"].status == "refused"
    assert "Cancel the run" in (by_id["job_000002"].detail or "")
    assert running.is_dir()


def test_http_endpoints_map_outcomes_to_status_codes(env) -> None:
    repository, service, _ = env
    _make_job(repository, "job_000001")
    _make_job(repository, "job_000099")

    response = _run(delete_job("job_000001", deletion=service))
    assert response.status_code == 204

    for job_id, expected in [("job_000001", 404), ("job_000099", 409), ("bad", 400)]:
        with pytest.raises(HTTPException) as info:
            _run(delete_job(job_id, deletion=service))
        assert info.value.status_code == expected

    bulk = _run(
        bulk_delete_jobs(JobBulkDeleteRequest(job_ids=["job_000099", "job_000002"]), deletion=service)
    )
    assert bulk.deleted == 0
    assert {r.job_id: r.status for r in bulk.results} == {
        "job_000099": "refused",
        "job_000002": "not_found",
    }


def test_bulk_request_validates_size() -> None:
    with pytest.raises(ValueError):
        JobBulkDeleteRequest(job_ids=[])
    with pytest.raises(ValueError):
        JobBulkDeleteRequest(job_ids=[f"job_{i:06d}" for i in range(101)])



def test_deleted_job_ids_are_never_reused(env) -> None:
    repository, service, _ = env
    _make_job(repository, "job_000001")
    _make_job(repository, "job_000002")
    _run(service.delete("job_000002"))
    assert repository.next_job_id() == "job_000003"

    # A repeated DELETE for the old id cannot hit the job created after it.
    new_root = _make_job(repository, repository.next_job_id())
    with pytest.raises(JobDeletionError):
        _run(service.delete("job_000002"))
    assert new_root.is_dir()

    _run(service.delete("job_000001"))  # lower number never lowers the mark
    assert repository.next_job_id() == "job_000004"


def test_high_water_mark_file_is_not_listed_as_a_job(env) -> None:
    repository, service, _ = env
    _make_job(repository, "job_000001")
    _run(service.delete("job_000001"))
    assert (repository.jobs_root / ".last_job_number").read_text() == "1"
    assert repository.list_all() == []
