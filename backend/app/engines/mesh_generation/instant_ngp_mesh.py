"""Instant-NGP mesh generation engine."""

from __future__ import annotations

import re
from pathlib import Path

import trimesh

from app.core.config import Settings, get_settings
from app.engines.instant_ngp.launcher import InstantNGPLauncher
from app.engines.instant_ngp.validation import validate_instant_ngp
from app.engines.mesh_generation.base import (
    ControlCallback,
    LogCallback,
    MeshGenerationEngine,
    MeshGenerationResult,
    ProgressCallback,
)
from app.jobs.repository import JobRepository
from app.jobs.structure import instant_ngp_snapshot_path, meshes_path
from app.models.job import Job

_VERT_TRI_RE = re.compile(r"#vertices=(\d+)\s+#triangles=(\d+)")


class InstantNGPMeshGenerationEngine(MeshGenerationEngine):
    """Wrap Instant-NGP mesh extraction via ``InstantNGPLauncher``."""

    name = "instant-ngp"

    def __init__(
        self,
        settings: Settings | None = None,
        repository: JobRepository | None = None,
        launcher: InstantNGPLauncher | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._repository = repository or JobRepository()
        self._launcher = launcher or InstantNGPLauncher(self._settings)

    def validate(self, job: Job) -> MeshGenerationResult:
        engine_error = self._validate_engine()
        if engine_error is not None:
            return engine_error

        snapshot = instant_ngp_snapshot_path(self._repository.jobs_root, job.id)
        if not snapshot.is_file():
            return MeshGenerationResult(
                success=False,
                message="Reconstruction snapshot not found for this job.",
                error_code="SNAPSHOT_NOT_FOUND",
            )

        return MeshGenerationResult(success=True, message="Validation passed.")

    def generate(
        self,
        job: Job,
        *,
        log: LogCallback | None = None,
        on_progress: ProgressCallback | None = None,
        check_control: ControlCallback | None = None,
    ) -> MeshGenerationResult:
        validation = self.validate(job)
        if not validation.success:
            return validation

        emit = _make_logger(log)
        progress = on_progress or (lambda _value: None)
        check = check_control or (lambda: None)

        jobs_root = self._repository.jobs_root
        snapshot = instant_ngp_snapshot_path(jobs_root, job.id)

        run_dir = meshes_path(jobs_root, job.id) / _safe_run_id()
        run_dir.mkdir(parents=True, exist_ok=False)
        ply_path = run_dir / "mesh.ply"
        obj_path = run_dir / "mesh.obj"
        glb_path = run_dir / "mesh.glb"

        emit("Loading snapshot...")
        progress(10)
        check()

        emit("Extracting mesh...")
        progress(25)
        check()

        vertex_count: int | None = None
        triangle_count: int | None = None

        def on_line(line: str) -> None:
            nonlocal vertex_count, triangle_count
            match = _VERT_TRI_RE.search(line)
            if match:
                vertex_count = int(match.group(1))
                triangle_count = int(match.group(2))

        try:
            return_code = self._launcher.extract_mesh(
                job_id=job.id,
                snapshot_path=snapshot,
                mesh_path=ply_path,
                on_line=on_line,
                check_control=check,
            )
        except RuntimeError as exc:
            emit(str(exc), level="error")
            return MeshGenerationResult(
                success=False,
                message=str(exc),
                error_code=_error_code_from_message(str(exc)),
            )

        if return_code != 0 or not ply_path.is_file():
            emit("Instant-NGP mesh extraction failed.", level="error")
            return MeshGenerationResult(
                success=False,
                message="Instant-NGP mesh extraction failed.",
                error_code="MESH_EXTRACTION_FAILED",
                data={"exit_code": return_code},
            )

        emit("Optimizing mesh...")
        progress(60)
        check()

        try:
            mesh = trimesh.load(str(ply_path), force="mesh")
            if hasattr(mesh, "process"):
                mesh.process(validate=True)
        except Exception as exc:
            emit(str(exc), level="error")
            return MeshGenerationResult(
                success=False,
                message=f"Failed to load extracted PLY: {exc}",
                error_code="MESH_EXTRACTION_FAILED",
            )

        if vertex_count is None:
            vertex_count = int(len(mesh.vertices))
        if triangle_count is None:
            triangle_count = int(len(mesh.faces))

        emit("Exporting OBJ...")
        progress(75)
        check()

        try:
            mesh.export(str(obj_path), file_type="obj")
        except Exception as exc:
            emit(str(exc), level="error")
            return MeshGenerationResult(
                success=False,
                message=f"OBJ export failed: {exc}",
                error_code="MESH_EXTRACTION_FAILED",
            )

        emit("Exporting GLB...")
        progress(90)
        check()

        try:
            mesh.export(str(glb_path), file_type="glb")
        except Exception as exc:
            emit(str(exc), level="error")
            return MeshGenerationResult(
                success=False,
                message=f"GLB export failed: {exc}",
                error_code="GLB_CONVERSION_FAILED",
            )

        progress(100)
        return MeshGenerationResult(
            success=True,
            message="Mesh generation completed.",
            data={
                "mesh_dir": run_dir.name,
                "mesh_ply": str(ply_path),
                "mesh_obj": str(obj_path),
                "mesh_glb": str(glb_path),
                "vertex_count": vertex_count,
                "triangle_count": triangle_count,
            },
        )

    def cancel(self, job: Job) -> MeshGenerationResult:
        if not self._launcher.cancel(job.id):
            return MeshGenerationResult(
                success=False,
                message="No active Instant-NGP mesh extraction for this job.",
                error_code="NOT_RUNNING",
            )
        return MeshGenerationResult(success=True, message="Instant-NGP mesh generation cancelled.")

    def _validate_engine(self) -> MeshGenerationResult | None:
        result = validate_instant_ngp(self._settings)
        if result.ready:
            return None
        return MeshGenerationResult(
            success=False,
            message=result.message or "Instant-NGP is not ready.",
            error_code=result.error_code or "INSTANT_NGP_UNAVAILABLE",
        )


def _make_logger(log: LogCallback | None):
    def emit(message: str, level: str = "info") -> None:
        if log is None:
            return
        try:
            log(message, level)
        except TypeError:
            log(message)

    return emit


def _safe_run_id() -> str:
    from app.models.job import utc_now_iso

    return utc_now_iso().replace(":", "").replace("+", "_").replace(".", "_")


def _error_code_from_message(message: str) -> str:
    if "Python version mismatch" in message:
        return "PYTHON_VERSION_MISMATCH"
    return "INSTANT_NGP_UNAVAILABLE"
