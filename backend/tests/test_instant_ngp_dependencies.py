"""Tests for Instant-NGP runtime Python dependencies."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.core.config import Settings
from app.engines.instant_ngp.launcher import InstantNGPLauncher


def _backend_venv_python() -> Path:
    return Path(__file__).resolve().parents[1] / ".venv" / "bin" / "python"


@pytest.mark.skipif(not _backend_venv_python().is_file(), reason="Backend venv not present")
def test_launcher_python_can_import_commentjson() -> None:
    """Instant-NGP run.py requires commentjson in the launcher interpreter."""
    settings = Settings(
        INSTANT_NGP_PYTHON="python",
        INSTANT_NGP_ROOT="engines/instant-ngp",
    )
    launcher = InstantNGPLauncher(settings)
    resolved = launcher._resolve_interpreter()

    completed = subprocess.run(
        [
            resolved,
            "-c",
            "import commentjson; print(getattr(commentjson, '__version__', 'ok'))",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert completed.stdout.strip()
