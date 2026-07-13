"""Instant-NGP installation and runtime validation."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import Settings, get_settings

_REQUIRED_CONFIG_FILES = (
    "configs/nerf/base.json",
    "configs/sdf/base.json",
)


@dataclass
class InstantNGPValidationResult:
    """Structured Instant-NGP validation outcome."""

    installed: bool = False
    compiled: bool = False
    python_bindings: bool = False
    python_version_match: bool = False
    ready: bool = False
    error_code: str | None = None
    message: str | None = None
    errors: list[str] = field(default_factory=list)
    details: dict[str, str] = field(default_factory=dict)

    def to_status_dict(self) -> dict[str, object]:
        """Public API shape for ``GET /api/system/engines``."""
        return {
            "installed": self.installed,
            "compiled": self.compiled,
            "python_bindings": self.python_bindings,
            "ready": self.ready,
        }


def validate_instant_ngp(settings: Settings | None = None) -> InstantNGPValidationResult:
    """Verify the local Instant-NGP engine is present and usable."""
    cfg = settings or get_settings()
    root = cfg.instant_ngp_path
    result = InstantNGPValidationResult(details={"root": str(root)})

    if not root.is_dir():
        result.errors.append(f"Instant-NGP directory not found: {root}")
        result.message = (
            "Instant-NGP is not installed. Expected at "
            f"{cfg.instant_ngp_root} relative to the workspace root."
        )
        result.error_code = "INSTANT_NGP_UNAVAILABLE"
        return result

    result.installed = True

    cmake_file = root / "CMakeLists.txt"
    if not cmake_file.is_file():
        result.errors.append(f"Missing CMakeLists.txt: {cmake_file}")
    else:
        result.details["cmake"] = str(cmake_file)

    build_dir = root / "build"
    if not build_dir.is_dir():
        result.errors.append(f"Build directory not found: {build_dir}")
        result.message = "Instant-NGP has not been compiled. Run CMake build in engines/instant-ngp."
        result.error_code = "INSTANT_NGP_UNAVAILABLE"
        return result

    result.compiled = True

    run_script = root / "scripts" / "run.py"
    if not run_script.is_file():
        result.errors.append(f"Missing run script: {run_script}")
        result.message = f"Instant-NGP run script not found: {run_script}"
        result.error_code = "INSTANT_NGP_UNAVAILABLE"
        return result

    for rel_config in _REQUIRED_CONFIG_FILES:
        config_path = root / rel_config
        if not config_path.is_file():
            result.errors.append(f"Missing configuration file: {rel_config}")

    binding = _find_pyngp_binding(build_dir)
    if binding is None:
        result.errors.append("pyngp Python bindings were not found in the build directory.")
        result.message = (
            "Instant-NGP Python bindings are missing. Build Instant-NGP before running reconstruction."
        )
        result.error_code = "INSTANT_NGP_UNAVAILABLE"
        return result

    result.python_bindings = True
    result.details["pyngp_binding"] = binding.name

    interpreter_path = _resolve_python_executable(cfg.instant_ngp_python)
    if interpreter_path is None:
        result.errors.append(
            f"Instant-NGP Python interpreter is not executable: {cfg.instant_ngp_python}"
        )
        result.message = (
            "Instant-NGP Python interpreter could not be executed. "
            "Set INSTANT_NGP_PYTHON to an absolute path or an executable available in the "
            "current environment."
        )
        result.error_code = "INSTANT_NGP_PYTHON_UNAVAILABLE"
        return result
    result.details["interpreter_path"] = interpreter_path

    binding_version = _python_version_from_binding(binding)
    interpreter_version = _python_version_from_interpreter(interpreter_path)
    result.details["binding_python"] = binding_version or "unknown"
    result.details["interpreter_python"] = interpreter_version or "unknown"

    if binding_version and interpreter_version and binding_version != interpreter_version:
        result.errors.append(
            "Configured Python interpreter does not match the compiled pyngp module "
            f"(binding: {binding_version}, interpreter: {interpreter_version})."
        )
        result.message = (
            f"Python version mismatch: pyngp was built for Python {binding_version}, "
            f"but {cfg.instant_ngp_python} is Python {interpreter_version}. "
            f"Set INSTANT_NGP_PYTHON to a Python {binding_version} interpreter or rebuild pyngp."
        )
        result.error_code = "PYTHON_VERSION_MISMATCH"
        return result

    if binding_version and interpreter_version:
        result.python_version_match = True

    if result.errors:
        result.message = result.errors[0]
        result.error_code = result.error_code or "INSTANT_NGP_UNAVAILABLE"
        return result

    result.ready = True
    result.message = "Instant-NGP is ready."
    return result


def _find_pyngp_binding(build_dir: Path) -> Path | None:
    candidates = sorted(build_dir.glob("pyngp*.so")) + sorted(build_dir.glob("pyngp*.pyd"))
    return candidates[0] if candidates else None


def _python_version_from_binding(binding: Path) -> str | None:
    match = re.search(r"cpython-(\d)(\d+)", binding.name)
    if not match:
        return None
    return f"{match.group(1)}.{match.group(2)}"


def _python_version_from_interpreter(python_executable: str) -> str | None:
    try:
        completed = subprocess.run(
            [
                python_executable,
                "-c",
                "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if completed.returncode != 0:
        return None

    version = completed.stdout.strip()
    return version or None


def _resolve_python_executable(python_executable: str) -> str | None:
    """Resolve ``python_executable`` into an executable path.

    If an absolute/relative filesystem path is provided, validate it exists.
    If a bare command is provided, resolve it via the current environment's PATH.
    """
    candidate = Path(python_executable)
    if candidate.is_file():
        return str(candidate.resolve())

    try:
        completed = subprocess.run(
            [python_executable, "-c", "import sys; print(sys.executable)"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if completed.returncode != 0:
        return None

    resolved = completed.stdout.strip()
    return resolved or None
