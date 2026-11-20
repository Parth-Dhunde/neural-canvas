"""Workspace path resolution.

All filesystem roots are resolved relative to the repository workspace root,
never hardcoded to platform-specific absolute paths.
"""

from functools import lru_cache
from pathlib import Path


def get_workspace_root() -> Path:
    """Return the repository workspace root directory.

    Discovers the root by walking upward from this module until both
    ``engines/instant-ngp`` and ``website/backend`` are present.
    """
    return _discover_workspace_root()


@lru_cache
def _discover_workspace_root() -> Path:
    start = Path(__file__).resolve().parent
    for candidate in (start, *start.parents):
        if (candidate / "engines" / "instant-ngp").is_dir() and (
            candidate / "website" / "backend"
        ).is_dir():
            return candidate
    # Fallback: website/backend/app/core/paths.py → workspace root
    return Path(__file__).resolve().parents[4]


def resolve_workspace_path(relative: str | Path) -> Path:
    """Return an absolute path under the workspace root."""
    return (get_workspace_root() / Path(relative)).resolve()
