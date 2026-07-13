"""System-wide startup validation and engine status."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import Settings, get_settings
from app.core.paths import get_workspace_root
from app.engines.instant_ngp.validation import InstantNGPValidationResult, validate_instant_ngp


@dataclass
class WorkspaceValidationResult:
    found: bool
    message: str


@dataclass
class SystemValidationResult:
    workspace: WorkspaceValidationResult
    instant_ngp: InstantNGPValidationResult
    backend_ready: bool = True
    errors: list[str] = field(default_factory=list)

    def to_api_dict(self) -> dict[str, object]:
        return {
            "workspace": {
                "found": self.workspace.found,
                "ready": self.workspace.found,
            },
            "instant_ngp": self.instant_ngp.to_status_dict(),
            "custom_nerf": {
                "installed": False,
            },
            "backend": {
                "ready": self.backend_ready,
            },
        }


_last_validation: SystemValidationResult | None = None


def get_last_validation() -> SystemValidationResult | None:
    return _last_validation


def run_startup_validation(settings: Settings | None = None) -> SystemValidationResult:
    """Validate workspace and engine installations without raising."""
    global _last_validation

    cfg = settings or get_settings()
    workspace_root = get_workspace_root()
    workspace = WorkspaceValidationResult(
        found=workspace_root.is_dir(),
        message="Workspace root found." if workspace_root.is_dir() else "Workspace root not found.",
    )

    instant_ngp = validate_instant_ngp(cfg)
    errors: list[str] = []
    if not workspace.found:
        errors.append(workspace.message)
    errors.extend(instant_ngp.errors)

    result = SystemValidationResult(
        workspace=workspace,
        instant_ngp=instant_ngp,
        backend_ready=True,
        errors=errors,
    )
    _last_validation = result
    return result


def log_startup_validation(result: SystemValidationResult, logger) -> None:
    """Emit human-readable startup validation lines."""
    workspace_mark = "✓ Found" if result.workspace.found else "✗ Missing"
    logger.info("Workspace:\n%s", workspace_mark)

    if result.instant_ngp.installed:
        logger.info("Instant-NGP:\n✓ Installed")
    else:
        logger.info("Instant-NGP:\n✗ Missing")

    if result.instant_ngp.compiled:
        logger.info("Build:\n✓ Found")
    else:
        logger.info("Build:\n✗ Missing")

    if result.instant_ngp.python_bindings:
        logger.info("Python Bindings:\n✓ Found")
    else:
        logger.info("Python Bindings:\n✗ Missing")

    if result.instant_ngp.ready:
        logger.info("Instant-NGP runtime:\n✓ Ready")
    else:
        logger.info("Instant-NGP runtime:\n✗ Not ready")
        if result.instant_ngp.message:
            logger.warning("Instant-NGP validation: %s", result.instant_ngp.message)

    logger.info("Backend:\nReady")
