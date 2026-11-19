"""Tests for Stage 7 export: manifest verification, mesh selection, download path safety."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import trimesh
from fastapi import HTTPException

from app.api.jobs import download_job_export, get_job_exports, get_job_mesh
from app.core.config import Settings
from app.engines.mesh_cleanup.trimesh_cleanup import TrimeshMeshCleanupEngine
from app.jobs.pipeline_repository import PipelineRepository
from app.jobs.repository import JobRepository
from app.models.job import Job
from app.pipeline.pipeline_manager import PipelineManager
from app.pipeline.pipeline_state import PipelineState
from app.pipeline.stage_registry import StageRegistry
from app.pipeline.stages.export_stage import ExportStage
from app.pipeline.stages.mesh_cleanup_stage import MeshCleanupStage
from app.services.export_service import ExportError, ExportService
from app.services.job_manager import JobManagerImpl
from app.services.mesh_cleanup_service import MeshCleanupService

JOB_ID = "job_000501"
RUN = "2026-10-15T090328_577266_0000"


@pytest.fixture
def env(tmp_path: Path):
    settings = Settings(JOBS_ROOT=str(tmp_path / "jobs"))
    repository = JobRepository(settings=settings)
    repository.create_folder_structure(JOB_ID)
    run_dir = repository.jobs_root / JOB_ID / "meshes" / RUN
    run_dir.mkdir(parents=True)
    mesh = trimesh.creation.icosphere(subdivisions=3)
    for fmt in ("ply", "obj", "glb"):
        mesh.export(str(run_dir / f"mesh.{fmt}"), file_type=fmt)
    repository.save(
        Job(id=JOB_ID, name=JOB_ID, engine="Instant-NGP", image_count=3, mesh_path=f"meshes/{RUN}/mesh.glb")
    )
    return settings, repository, run_dir


def _clean(settings: Settings, repository: JobRepository) -> dict:
    service = MeshCleanupService(
        repository, TrimeshMeshCleanupEngine(settings=settings, repository=repository)
    )
    return asyncio.run(service.clean(JOB_ID))


def test_manifest_prefers_original_before_cleanup(env) -> None:
    _, repository, _ = env
    manifest = ExportService(repository).manifest(repository.get(JOB_ID))
    assert manifest["preferred"] == "original"
    assert manifest["viewer_url"] == f"/api/jobs/{JOB_ID}/exports/original/glb"
    assert manifest["variants"]["original"]["complete"] is True
    assert manifest["variants"]["cleaned"]["formats"] == {}
    assert manifest["variants"]["cleaned"]["unavailable_reason"] == "mesh cleanup has not run"


def test_manifest_prefers_cleaned_after_successful_cleanup(env) -> None:
    settings, repository, _ = env
    _clean(settings, repository)
    manifest = ExportService(repository).manifest(repository.get(JOB_ID))
    assert manifest["preferred"] == "cleaned"
    assert manifest["variants"]["cleaned"]["complete"] is True
    assert manifest["variants"]["original"]["complete"] is True  # originals stay downloadable
    for fmt in ("ply", "obj", "glb"):
        entry = manifest["variants"]["cleaned"]["formats"][fmt]
        assert entry["url"] == f"/api/jobs/{JOB_ID}/exports/cleaned/{fmt}" and entry["bytes"] > 0


def test_corrupt_cleaned_glb_falls_back_to_original(env) -> None:
    settings, repository, _ = env
    summary = _clean(settings, repository)
    glb = repository.jobs_root / JOB_ID / summary["output"]["files"]["glb"]["path"]
    glb.write_bytes(b"not a glb")
    manifest = ExportService(repository).manifest(repository.get(JOB_ID))
    assert manifest["preferred"] == "original"
    assert manifest["variants"]["cleaned"]["formats"]["glb"]["problem"] == "file is not a valid GLB"


def test_failed_or_stale_cleanup_is_not_used(env) -> None:
    settings, repository, _ = env
    _clean(settings, repository)
    job = repository.get(JOB_ID)
    stale = Job.from_dict({**job.to_dict(), "mesh_path": "meshes/newer_run/mesh.glb"})
    manifest = ExportService(repository).manifest(stale)
    assert manifest["variants"]["cleaned"]["unavailable_reason"] == "cleanup belongs to an older Stage 5 mesh"
    failed = Job.from_dict({**job.to_dict(), "mesh_cleanup": {"status": "failed", "error": "boom"}})
    manifest = ExportService(repository).manifest(failed)
    assert manifest["preferred"] == "original"
    assert manifest["variants"]["cleaned"]["unavailable_reason"] == "cleanup failed: boom"


def test_paths_outside_job_directory_are_never_served(env, tmp_path: Path) -> None:
    settings, repository, _ = env
    _clean(settings, repository)
    secret = tmp_path / "secret.glb"
    secret.write_bytes(b"glTF-secret")
    job = repository.get(JOB_ID)
    job.mesh_cleanup["output"]["files"]["glb"]["path"] = "../../secret.glb"
    repository.save(job)
    service = ExportService(repository)
    entry = service.manifest(repository.get(JOB_ID))["variants"]["cleaned"]["formats"]["glb"]
    assert entry["available"] is False and "outside the job directory" in entry["problem"]
    with pytest.raises(ExportError):
        service.resolve_download(repository.get(JOB_ID), "cleaned", "glb")


@pytest.mark.parametrize("job_id", ["job_../job_000501", "../jobs", "job_1", "job_000501/../x"])
def test_invalid_job_ids_are_rejected(env, job_id: str) -> None:
    _, repository, _ = env
    with pytest.raises(ExportError, match="Invalid job id"):
        ExportService(repository).require_job(job_id)


def test_unknown_variant_or_format_is_rejected(env) -> None:
    _, repository, _ = env
    service = ExportService(repository)
    for variant, fmt in (("cleaned", "stl"), ("raw", "glb")):
        with pytest.raises(ExportError):
            service.resolve_download(repository.get(JOB_ID), variant, fmt)


def test_export_routes_serve_verified_files(env) -> None:
    settings, repository, _ = env
    _clean(settings, repository)
    service = ExportService(repository)
    manifest = asyncio.run(get_job_exports(JOB_ID, exports=service))
    assert manifest["preferred"] == "cleaned"
    response = asyncio.run(download_job_export(JOB_ID, "cleaned", "glb", exports=service))
    assert Path(response.path).read_bytes()[:4] == b"glTF"
    assert response.media_type == "model/gltf-binary"
    assert f'{JOB_ID}_cleaned.glb' in response.headers["content-disposition"]
    original = asyncio.run(download_job_export(JOB_ID, "original", "ply", exports=service))
    assert Path(original.path).name == "mesh.ply" and RUN in str(original.path)
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(get_job_exports("job_999999", exports=service))
    assert excinfo.value.status_code == 404


def test_legacy_mesh_endpoint_still_serves_stage5_glb(env) -> None:
    settings, repository, run_dir = env
    _clean(settings, repository)
    response = asyncio.run(get_job_mesh(JOB_ID, manager=JobManagerImpl(repository)))
    assert Path(response.path) == (run_dir / "mesh.glb").resolve()


def _manager(settings: Settings, repository: JobRepository) -> tuple[PipelineManager, PipelineState]:
    state = PipelineState(PipelineRepository(settings))
    cleanup = MeshCleanupService(repository, TrimeshMeshCleanupEngine(settings=settings, repository=repository))
    registry = StageRegistry(
        stages=[
            MeshCleanupStage(service=cleanup, pipeline_state=state),
            ExportStage(service=ExportService(repository), repository=repository, pipeline_state=state),
        ]
    )
    manager = PipelineManager(registry=registry, state=state, repository=repository)
    document = manager.initialize(JOB_ID)
    for stage in document["stages"]:
        if stage["id"] <= 5:
            stage.update(status="completed", progress=100)
    state.save(JOB_ID, document)
    return manager, state


def test_stage6_then_stage7_through_pipeline_manager(env) -> None:
    settings, repository, _ = env
    manager, state = _manager(settings, repository)
    assert asyncio.run(manager.run_stage(JOB_ID, 6)).stopped_reason == "completed"
    assert asyncio.run(manager.run_stage(JOB_ID, 7)).stopped_reason == "completed"
    statuses = {s["id"]: s["status"] for s in state.load(JOB_ID)["stages"]}
    assert statuses[6] == "completed" and statuses[7] == "completed"
    job = repository.get(JOB_ID)
    assert job.exports["preferred"] == "cleaned"
    assert job.exports["available"] == {"original": ["ply", "obj", "glb"], "cleaned": ["ply", "obj", "glb"]}
    written = json.loads((repository.jobs_root / JOB_ID / "exports" / "manifest.json").read_text())
    assert written["preferred"] == "cleaned" and "generated_at" in written


def test_stage7_rejects_corrupt_cleaned_glb_and_keeps_originals(env) -> None:
    settings, repository, run_dir = env
    manager, state = _manager(settings, repository)
    asyncio.run(manager.run_stage(JOB_ID, 6))
    glb = repository.jobs_root / JOB_ID / repository.get(JOB_ID).mesh_cleanup["output"]["files"]["glb"]["path"]
    glb.write_bytes(b"corrupted")
    result = asyncio.run(manager.run_stage(JOB_ID, 7))
    assert result.stopped_reason == "stage_failed"
    assert "glb" in state.load(JOB_ID)["execution"]["last_error"]
    assert not (repository.jobs_root / JOB_ID / "exports" / "manifest.json").exists()
    service = ExportService(repository)
    manifest = service.manifest(repository.get(JOB_ID))
    assert manifest["preferred"] == "original"
    assert service.resolve_download(repository.get(JOB_ID), "original", "glb") == (run_dir / "mesh.glb").resolve()


def test_failed_cleanup_reason_mentions_kept_previous_success(env) -> None:
    settings, repository, _ = env
    summary = _clean(settings, repository)
    job = repository.get(JOB_ID)
    job.mesh_cleanup = {"status": "failed", "error": "boom", "previous_success": job.mesh_cleanup}
    manifest = ExportService(repository).manifest(job)
    reason = manifest["variants"]["cleaned"]["unavailable_reason"]
    assert manifest["preferred"] == "original"
    assert summary["cleanup_id"] in reason and "not modified" in reason


def test_stage7_fails_when_cleaned_files_disappear(env) -> None:
    settings, repository, _ = env
    manager, state = _manager(settings, repository)
    asyncio.run(manager.run_stage(JOB_ID, 6))
    obj = repository.jobs_root / JOB_ID / repository.get(JOB_ID).mesh_cleanup["output"]["files"]["obj"]["path"]
    obj.unlink()
    result = asyncio.run(manager.run_stage(JOB_ID, 7))
    assert result.stopped_reason == "stage_failed"
    assert "obj" in state.load(JOB_ID)["execution"]["last_error"]
