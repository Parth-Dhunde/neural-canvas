"""Mesh cleanup engine: reads the Stage 5 mesh and writes cleaned exports beside it.

Layout (Stage 5 files are never modified)::

    meshes/<run>/mesh.{ply,obj,glb}                  # Stage 5 originals
    meshes/<run>/cleanup/<cleanup_id>/mesh.{ply,obj,glb}
    meshes/<run>/cleanup/<cleanup_id>/cleanup.json  # parameters, validation, counts

Outputs are written to a hidden temporary directory, re-loaded and validated, and only then
renamed into place, so a failed or partial run can never look like a successful cleanup.
"""

from __future__ import annotations

import json
import shutil
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import trimesh

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.engines.mesh_cleanup.base import (
    ControlCallback,
    LogCallback,
    MeshCleanupEngine,
    MeshCleanupResult,
    ProgressCallback,
)
from app.engines.mesh_cleanup.processing import (
    CleanupParameters,
    MeshCleanupError,
    clean_mesh,
)
from app.jobs.repository import JobRepository
from app.jobs.structure import (
    MESH_CLEANUP_DIR,
    MESH_CLEANUP_REPORT_FILE,
    MESH_FORMATS,
    MESH_PLY_FILE,
    job_root_path,
)
from app.models.job import Job, utc_now_iso
from app.pipeline.pipeline_manager import PipelineControlError

logger = get_logger(__name__)


def parameters_from_settings(settings: Settings) -> CleanupParameters:
    return CleanupParameters(
        taubin_iterations=settings.mesh_cleanup_taubin_iterations,
        taubin_lambda=settings.mesh_cleanup_taubin_lambda,
        taubin_nu=settings.mesh_cleanup_taubin_nu,
        smooth_min_component_faces=settings.mesh_cleanup_smooth_min_component_faces,
        min_component_faces=settings.mesh_cleanup_min_component_faces,
        decimate_min_faces=settings.mesh_cleanup_decimate_min_faces,
        decimate_max_faces=settings.mesh_cleanup_decimate_max_faces,
    )


def _within(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def verify_mesh_file(path: Path, expected_faces: int | None = None) -> dict[str, Any]:
    """Re-load an exported mesh file and check it is complete and finite."""
    if not path.is_file() or path.stat().st_size == 0:
        raise MeshCleanupError(f"{path.name} was not written")
    loaded = trimesh.load(str(path), force="mesh", process=False)
    vertices = np.asarray(loaded.vertices)
    faces = np.asarray(loaded.faces)
    if len(vertices) == 0 or len(faces) == 0:
        raise MeshCleanupError(f"{path.name} contains no geometry")
    if not np.isfinite(vertices).all():
        raise MeshCleanupError(f"{path.name} contains NaN/inf vertices")
    if expected_faces is not None and len(faces) != expected_faces:
        raise MeshCleanupError(
            f"{path.name} has {len(faces)} faces after re-loading, expected {expected_faces}"
        )
    return {"bytes": path.stat().st_size, "vertices": int(len(vertices)), "faces": int(len(faces))}


class TrimeshMeshCleanupEngine(MeshCleanupEngine):
    """Validate, repair, smooth and decimate the Stage 5 mesh with trimesh."""

    name = "trimesh"

    def __init__(
        self,
        settings: Settings | None = None,
        repository: JobRepository | None = None,
        params: CleanupParameters | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._repository = repository or JobRepository(self._settings)
        self._params = params or parameters_from_settings(self._settings)

    def source_paths(self, job: Job) -> tuple[Path, Path] | None:
        """Return (run directory, source PLY) for the job's Stage 5 mesh, if it is safe."""
        if not job.mesh_path:
            return None
        root = job_root_path(self._repository.jobs_root, job.id)
        run_dir = (root / Path(job.mesh_path)).parent
        source = run_dir / MESH_PLY_FILE
        if not _within(root, run_dir) or not _within(root, source):
            return None
        return run_dir, source

    def validate(self, job: Job) -> MeshCleanupResult:
        try:
            self._params.validate()
        except ValueError as exc:
            return MeshCleanupResult(False, f"Invalid cleanup parameters: {exc}", "INVALID_PARAMETERS")
        paths = self.source_paths(job)
        if paths is None:
            return MeshCleanupResult(
                False,
                "No Stage 5 mesh is recorded for this job. Run mesh generation first.",
                "SOURCE_MESH_MISSING",
            )
        _, source = paths
        if not source.is_file() or source.stat().st_size == 0:
            return MeshCleanupResult(
                False, f"Stage 5 source mesh not found: {source.name}", "SOURCE_MESH_MISSING"
            )
        return MeshCleanupResult(True, "Validation passed.", data={"source": str(source)})

    def clean(
        self,
        job: Job,
        *,
        log: LogCallback | None = None,
        on_progress: ProgressCallback | None = None,
        check_control: ControlCallback | None = None,
    ) -> MeshCleanupResult:
        validation = self.validate(job)
        if not validation.success:
            return validation

        emit = _make_logger(log)
        progress = on_progress or (lambda _value: None)
        check = check_control or (lambda: None)

        root = job_root_path(self._repository.jobs_root, job.id)
        run_dir, source = self.source_paths(job)  # type: ignore[misc]
        cleanup_id = utc_now_iso().replace(":", "").replace("+", "_").replace(".", "_")
        cleanup_root = run_dir / MESH_CLEANUP_DIR
        final_dir = cleanup_root / cleanup_id
        temp_dir = cleanup_root / f".tmp-{cleanup_id}-{uuid.uuid4().hex[:8]}"

        try:
            check()
            emit(f"Loading Stage 5 mesh {source.relative_to(root)}")
            mesh = trimesh.load(str(source), force="mesh", process=False)
            progress(10)

            check()
            emit(
                f"Cleaning {len(mesh.vertices)} vertices / {len(mesh.faces)} faces "
                f"(params: {json.dumps(self._params.to_dict())})"
            )
            outcome = clean_mesh(mesh, self._params)
            progress(60)
            for name, info in outcome.steps.items():
                emit(f"{name}: {json.dumps(info)}")
            for warning in outcome.warnings:
                emit(warning, "warn")

            check()
            temp_dir.mkdir(parents=True, exist_ok=False)
            files: dict[str, dict[str, Any]] = {}
            expected_faces = len(outcome.mesh.faces)
            for index, fmt in enumerate(MESH_FORMATS):
                check()
                path = temp_dir / f"mesh.{fmt}"
                emit(f"Exporting cleaned {fmt.upper()}...")
                outcome.mesh.export(str(path), file_type=fmt)
                info = verify_mesh_file(path, expected_faces)
                files[fmt] = {"path": str((final_dir / path.name).relative_to(root)), **info}
                progress(65 + 10 * (index + 1))

            report = {
                "status": "succeeded",
                "cleanup_id": cleanup_id,
                "completed_at": utc_now_iso(),
                "source": {
                    "dir": str(run_dir.relative_to(root)),
                    "ply": str(source.relative_to(root)),
                    "vertices": int(outcome.input_validation.vertices),
                    "faces": int(outcome.input_validation.faces),
                },
                "output": {
                    "dir": str(final_dir.relative_to(root)),
                    "vertices": int(len(outcome.mesh.vertices)),
                    "faces": expected_faces,
                    "files": files,
                },
                "parameters": self._params.to_dict(),
                "steps": outcome.steps,
                "validation": {
                    "input": outcome.input_validation.to_dict(),
                    "output": outcome.output_validation.to_dict(),
                },
                "warnings": outcome.warnings,
            }
            (temp_dir / MESH_CLEANUP_REPORT_FILE).write_text(
                json.dumps(report, indent=2, default=_json_default), encoding="utf-8"
            )
            check()
            # Publish atomically: only a fully written and verified directory gets its final name.
            temp_dir.rename(final_dir)
            progress(100)
            emit(
                f"Cleanup complete: {report['source']['faces']} -> {expected_faces} faces, "
                f"written to {final_dir.relative_to(root)}"
            )
            return MeshCleanupResult(True, "Mesh cleanup complete.", data=report)
        except PipelineControlError:
            _discard(temp_dir)
            raise
        except MeshCleanupError as exc:
            _discard(temp_dir)
            emit(f"Mesh cleanup failed: {exc}", "error")
            return MeshCleanupResult(False, str(exc), "CLEANUP_FAILED")
        except Exception as exc:  # unexpected trimesh/IO failure: keep originals, report clearly
            _discard(temp_dir)
            logger.exception("Mesh cleanup failed | job_id=%s", job.id)
            emit(f"Mesh cleanup failed: {exc}", "error")
            return MeshCleanupResult(False, f"Mesh cleanup failed: {exc}", "CLEANUP_FAILED")


def _discard(temp_dir: Path) -> None:
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Not JSON serializable: {type(value).__name__}")


def _make_logger(log: LogCallback | None) -> Callable[..., None]:
    def emit(message: str, level: str = "info") -> None:
        if log is None:
            return
        try:
            log(message, level)
        except TypeError:
            log(message)

    return emit
