"""Filesystem-safe removal of a single job workspace.

A job is deleted in two steps:

1. Its directory is renamed (atomically, inside the jobs root) to a ``.deleting-*`` name, so it
   disappears from every listing at once and a repeated request finds nothing to delete.
2. The renamed directory is removed with ``shutil.rmtree``, which on this platform uses
   file-descriptor based traversal: symbolic links inside the workspace are unlinked, never
   followed, so nothing outside the job directory can be touched.

If step 2 is interrupted (crash, power loss), the ``.deleting-*`` directory is removed by
``purge_deletion_leftovers`` on the next deletion or backend start.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from app.core.logging import get_logger
from app.jobs.repository import JOB_ID_PATTERN

logger = get_logger(__name__)

TRASH_PREFIX = ".deleting-"


class JobDeletionError(Exception):
    """Deletion refused or failed. ``code`` is one of: invalid, not_found, running,
    protected, unsafe, failed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_job_id(job_id: str) -> str:
    """Accept only canonical identifiers such as ``job_000001`` (no separators, no ``..``)."""
    if not isinstance(job_id, str) or not JOB_ID_PATTERN.fullmatch(job_id):
        raise JobDeletionError("invalid", f"Invalid job id: {job_id!r}")
    return job_id


def resolve_job_directory(jobs_root: Path, job_id: str) -> Path | None:
    """Return the job's directory if it exists and is a real directory directly inside
    ``jobs_root``; ``None`` if it does not exist. Raises for anything unsafe."""
    validate_job_id(job_id)
    root = jobs_root.resolve()
    candidate = root / job_id
    if not os.path.lexists(candidate):
        return None
    if candidate.is_symlink():
        raise JobDeletionError(
            "unsafe", f"{job_id} is a symbolic link; it was not deleted for safety."
        )
    if not candidate.is_dir():
        raise JobDeletionError("unsafe", f"{job_id} is not a directory; it was not deleted.")
    resolved = candidate.resolve(strict=True)
    if resolved.parent != root or resolved.name != job_id:
        raise JobDeletionError("unsafe", f"{job_id} resolves outside the jobs directory.")
    return resolved


def _require_safe_rmtree() -> None:
    if not getattr(shutil.rmtree, "avoids_symlink_attacks", False):
        raise JobDeletionError(
            "unsafe",
            "This platform's directory removal can follow symbolic links; deletion is disabled.",
        )


def _remove_trash_directory(jobs_root: Path, trash: Path) -> None:
    root = jobs_root.resolve()
    if trash.parent != root or not trash.name.startswith(TRASH_PREFIX) or trash.is_symlink():
        raise JobDeletionError("unsafe", "Refusing to remove an unexpected path.")
    shutil.rmtree(trash)


def move_to_trash(jobs_root: Path, job_directory: Path, job_id: str) -> Path:
    """Atomically rename the job directory out of the listing; return the new path."""
    _require_safe_rmtree()
    root = jobs_root.resolve()
    if job_directory.parent != root or job_directory.name != job_id:
        raise JobDeletionError("unsafe", f"{job_id} is not directly inside the jobs directory.")
    trash = root / f"{TRASH_PREFIX}{job_id}-{uuid.uuid4().hex}"
    os.rename(job_directory, trash)
    return trash


def remove_trash(jobs_root: Path, trash: Path) -> bool:
    """Remove a renamed job directory. Returns False (and logs) if removal did not finish;
    the leftover is purged later."""
    try:
        _remove_trash_directory(jobs_root, trash)
        return True
    except (OSError, JobDeletionError) as exc:
        logger.warning("Job files could not be fully removed yet (%s); will retry.", exc)
        return False


def purge_deletion_leftovers(jobs_root: Path) -> int:
    """Remove ``.deleting-*`` directories left by interrupted deletions. Returns the count."""
    root = jobs_root.resolve()
    if not root.is_dir() or not getattr(shutil.rmtree, "avoids_symlink_attacks", False):
        return 0
    removed = 0
    for entry in root.iterdir():
        if not entry.name.startswith(TRASH_PREFIX) or entry.is_symlink() or not entry.is_dir():
            continue
        if remove_trash(root, entry):
            removed += 1
    return removed
