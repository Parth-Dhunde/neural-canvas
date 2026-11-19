"""Mesh export manifest and safe download resolution (Stage 7 and export API).

Every answer is based on the files actually present: a variant is only offered when its file
exists inside the job directory, is non-empty and has the expected format header. The cleaned
variant additionally requires a succeeded Stage 6 cleanup of the *current* Stage 5 run.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from app.jobs.repository import JOB_ID_PATTERN, JobRepository
from app.jobs.structure import (
    EXPORT_MANIFEST_FILE,
    EXPORTS_DIR,
    MESH_FORMATS,
    job_root_path,
)
from app.models.job import Job, utc_now_iso

Variant = Literal["cleaned", "original"]
VARIANTS: tuple[Variant, ...] = ("cleaned", "original")

MEDIA_TYPES = {
    "glb": "model/gltf-binary",
    "obj": "model/obj",
    "ply": "application/octet-stream",
}


class ExportError(Exception):
    """Raised when a requested export is unavailable or unsafe."""


def _header_ok(path: Path, fmt: str) -> bool:
    try:
        with path.open("rb") as handle:
            head = handle.read(64)
    except OSError:
        return False
    if fmt == "glb":
        return head[:4] == b"glTF"
    if fmt == "ply":
        return head[:3] == b"ply"
    if fmt == "obj":
        return len(head.strip()) > 0
    return False


def _resolve_inside(root: Path, relative: str | None) -> Path | None:
    if not relative:
        return None
    candidate = (root / Path(relative)).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _check_file(root: Path, relative: str | None, fmt: str) -> dict[str, Any]:
    path = _resolve_inside(root, relative)
    entry: dict[str, Any] = {"path": relative, "available": False, "bytes": 0}
    if path is None:
        entry["problem"] = "path is missing or outside the job directory"
        return entry
    if not path.is_file():
        entry["problem"] = "file not found"
        return entry
    size = path.stat().st_size
    entry["bytes"] = size
    if size == 0 or not os.access(path, os.R_OK):
        entry["problem"] = "file is empty or unreadable"
        return entry
    if not _header_ok(path, fmt):
        entry["problem"] = f"file is not a valid {fmt.upper()}"
        return entry
    entry["available"] = True
    return entry


def cleanup_is_current(job: Job) -> bool:
    """True when Stage 6 succeeded on the Stage 5 run that ``job.mesh_path`` points to."""
    cleanup = job.mesh_cleanup or {}
    if cleanup.get("status") != "succeeded" or not job.mesh_path:
        return False
    source_dir = (cleanup.get("source") or {}).get("dir")
    return source_dir is not None and Path(source_dir) == Path(job.mesh_path).parent


class ExportService:
    """Build export manifests and resolve download paths for a job."""

    def __init__(self, repository: JobRepository | None = None) -> None:
        self._repository = repository or JobRepository()

    def require_job(self, job_id: str) -> Job:
        if not JOB_ID_PATTERN.match(job_id):
            raise ExportError(f"Invalid job id: {job_id}")
        job = self._repository.get(job_id)
        if job is None:
            raise ExportError(f"Job not found: {job_id}")
        return job

    def manifest(self, job: Job) -> dict[str, Any]:
        root = job_root_path(self._repository.jobs_root, job.id)
        variants: dict[str, Any] = {}

        original: dict[str, Any] = {}
        if job.mesh_path:
            run_dir = Path(job.mesh_path).parent
            for fmt in MESH_FORMATS:
                original[fmt] = _check_file(root, str(run_dir / f"mesh.{fmt}"), fmt)
        variants["original"] = {"source": "stage5", "formats": original}

        cleanup = job.mesh_cleanup or {}
        cleaned: dict[str, Any] = {}
        cleaned_reason: str | None = None
        if cleanup_is_current(job):
            files = (cleanup.get("output") or {}).get("files") or {}
            for fmt in MESH_FORMATS:
                cleaned[fmt] = _check_file(root, (files.get(fmt) or {}).get("path"), fmt)
        elif cleanup.get("status") == "failed":
            cleaned_reason = f"cleanup failed: {cleanup.get('error')}"
            previous = cleanup.get("previous_success") or {}
            if previous.get("output", {}).get("dir"):
                cleaned_reason += (
                    f" (previous successful cleanup {previous.get('cleanup_id')} is kept at "
                    f"{previous['output']['dir']} and was not modified)"
                )
        elif cleanup.get("status") == "succeeded":
            cleaned_reason = "cleanup belongs to an older Stage 5 mesh"
        else:
            cleaned_reason = "mesh cleanup has not run"
        variants["cleaned"] = {
            "source": "stage6",
            "cleanup_id": cleanup.get("cleanup_id") if cleanup_is_current(job) else None,
            "formats": cleaned,
            "unavailable_reason": cleaned_reason,
        }

        for name, variant in variants.items():
            for fmt, entry in variant["formats"].items():
                if entry["available"]:
                    entry["url"] = f"/api/jobs/{job.id}/exports/{name}/{fmt}"
            variant["complete"] = bool(variant["formats"]) and all(
                entry["available"] for entry in variant["formats"].values()
            )

        preferred: str | None = None
        if variants["cleaned"]["formats"].get("glb", {}).get("available"):
            preferred = "cleaned"
        elif variants["original"]["formats"].get("glb", {}).get("available"):
            preferred = "original"

        return {
            "job_id": job.id,
            "preferred": preferred,
            "viewer_url": f"/api/jobs/{job.id}/exports/{preferred}/glb" if preferred else None,
            "variants": variants,
        }

    def resolve_download(self, job: Job, variant: str, fmt: str) -> Path:
        """Return the verified on-disk file for a variant/format, or raise ``ExportError``."""
        if variant not in VARIANTS or fmt not in MESH_FORMATS:
            raise ExportError(f"Unknown export {variant}/{fmt}")
        entry = self.manifest(job)["variants"][variant]["formats"].get(fmt)
        if not entry or not entry["available"]:
            reason = (entry or {}).get("problem") or "not available"
            raise ExportError(f"{variant} {fmt.upper()} is {reason}")
        root = job_root_path(self._repository.jobs_root, job.id)
        path = _resolve_inside(root, entry["path"])
        if path is None:
            raise ExportError("Invalid export path")
        return path

    def write_manifest(self, job: Job) -> dict[str, Any]:
        """Persist the verified manifest to ``exports/manifest.json`` (atomic replace)."""
        manifest = {**self.manifest(job), "generated_at": utc_now_iso()}
        exports_dir = job_root_path(self._repository.jobs_root, job.id) / EXPORTS_DIR
        exports_dir.mkdir(parents=True, exist_ok=True)
        target = exports_dir / EXPORT_MANIFEST_FILE
        temp = exports_dir / f".{EXPORT_MANIFEST_FILE}.tmp"
        temp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        os.replace(temp, target)
        return manifest


def get_export_service() -> ExportService:
    """FastAPI dependency that returns an export service instance."""
    return ExportService()
