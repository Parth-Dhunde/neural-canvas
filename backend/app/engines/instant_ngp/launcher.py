"""Instant-NGP process launcher — the only module that executes Instant-NGP subprocesses."""

from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.engines.instant_ngp.validation import validate_instant_ngp

logger = get_logger(__name__)

_active_processes: dict[str, subprocess.Popen[str]] = {}
_process_lock = threading.Lock()


class InstantNGPLauncher:
    """Execute Instant-NGP via upstream ``scripts/run.py``."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def root(self) -> Path:
        return self._settings.instant_ngp_path

    @property
    def run_script(self) -> Path:
        return self.root / "scripts" / "run.py"

    def validate_runtime(self):
        """Return structured validation for the configured Instant-NGP install."""
        return validate_instant_ngp(self._settings)

    def build_env(self) -> dict[str, str]:
        # Inherit current process environment so mise-managed shells work.
        env = os.environ.copy()
        build_path = str(self.root / "build")
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join([build_path, existing]).strip(os.pathsep)
        # Stream run.py output line by line instead of in block-buffered chunks.
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def run_training(
        self,
        *,
        job_id: str,
        scene_dir: Path,
        snapshot_path: Path,
        log_path: Path,
        on_line: Callable[[str], None] | None = None,
        check_control: Callable[[], None] | None = None,
    ) -> int:
        """Train a scene and write ``snapshot_path``."""
        args = [
            "--scene",
            str(scene_dir),
            "--n_steps",
            str(self._settings.instant_ngp_n_steps),
            "--save_snapshot",
            str(snapshot_path),
        ]
        return self._run(
            args,
            job_id=job_id,
            log_path=log_path,
            on_line=on_line,
            check_control=check_control,
        )

    def extract_mesh(
        self,
        *,
        job_id: str,
        snapshot_path: Path,
        mesh_path: Path,
        on_line: Callable[[str], None] | None = None,
        check_control: Callable[[], None] | None = None,
    ) -> int:
        """Extract a mesh from a trained snapshot."""
        args = [
            "--load_snapshot",
            str(snapshot_path),
            "--save_mesh",
            str(mesh_path),
            "--marching_cubes_res",
            str(self._settings.mesh_resolution),
            "--marching_cubes_density_thresh",
            str(self._settings.mesh_density_threshold),
        ]
        return self._run(
            args,
            job_id=job_id,
            on_line=on_line,
            check_control=check_control,
        )

    def active_pid(self, job_id: str) -> int | None:
        """Return the PID of the running Instant-NGP process for ``job_id``, if any."""
        with _process_lock:
            process = _active_processes.get(job_id)
        if process is None or process.poll() is not None:
            return None
        return process.pid

    def cancel(self, job_id: str) -> bool:
        """Terminate an active Instant-NGP process for ``job_id``."""
        with _process_lock:
            process = _active_processes.get(job_id)

        if process is None or process.poll() is not None:
            return False

        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()

        with _process_lock:
            _active_processes.pop(job_id, None)
        return True

    def _run(
        self,
        args: list[str],
        *,
        job_id: str,
        log_path: Path | None = None,
        on_line: Callable[[str], None] | None = None,
        check_control: Callable[[], None] | None = None,
    ) -> int:
        validation = self.validate_runtime()
        if not validation.ready:
            message = validation.message or "Instant-NGP is not ready."
            if on_line is not None:
                on_line(message)
            raise RuntimeError(message)

        interpreter = self._resolve_interpreter()
        command = [interpreter, str(self.run_script), *args]
        env = self.build_env()
        check = check_control or (lambda: None)

        try:
            process = subprocess.Popen(
                command,
                cwd=str(self.root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
        except OSError as exc:
            # Deterministic failure when configured interpreter cannot execute.
            raise RuntimeError(
                f"Instant-NGP Python interpreter is not executable: {interpreter} ({exc})"
            ) from exc

        with _process_lock:
            _active_processes[job_id] = process

        log_handle = log_path.open("w", encoding="utf-8") if log_path is not None else None
        return_code = 1

        try:
            assert process.stdout is not None
            for line in process.stdout:
                if log_handle is not None:
                    log_handle.write(line)
                    log_handle.flush()
                stripped = line.strip()
                if stripped:
                    logger.info("Instant-NGP | job_id=%s | %s", job_id, stripped)
                    if on_line is not None:
                        on_line(stripped)
                check()
            return_code = process.wait()
        finally:
            if log_handle is not None:
                log_handle.close()
            with _process_lock:
                _active_processes.pop(job_id, None)

        return return_code

    def _resolve_interpreter(self) -> str:
        """Resolve configured interpreter to an explicit path.

        Uses the current process environment (including PATH) to allow mise-managed
        environments, but never assumes a default like ``python3``.
        """
        candidates = self._interpreter_candidates()
        for interpreter in candidates:
            if self._interpreter_can_import(interpreter, "commentjson"):
                return interpreter

        raise RuntimeError(
            "Instant-NGP Python interpreter is missing runtime dependency commentjson. "
            f"Tried: {', '.join(candidates)}. "
            "Install it in that environment (for example: "
            "'<python> -m pip install commentjson') or set INSTANT_NGP_PYTHON to the "
            "backend virtualenv python."
        )

    def _interpreter_candidates(self) -> list[str]:
        """Return interpreter paths to try, preserving venv shims."""
        configured = self._settings.instant_ngp_python
        candidates: list[str] = []

        configured_path = Path(configured)
        if configured_path.is_file():
            candidates.append(str(configured_path))

        backend_venv = Path(__file__).resolve().parents[3] / ".venv" / "bin" / "python"
        if backend_venv.is_file():
            venv_python = str(backend_venv)
            if venv_python not in candidates:
                candidates.append(venv_python)

        if not candidates:
            try:
                completed = subprocess.run(
                    [configured, "-c", "import sys; print(sys.executable)"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                    env=os.environ.copy(),
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise RuntimeError(
                    "Instant-NGP Python interpreter could not be executed. "
                    "Set INSTANT_NGP_PYTHON to an absolute path or an executable available "
                    "in the current environment."
                ) from exc

            resolved = completed.stdout.strip() if completed.returncode == 0 else ""
            if not resolved:
                raise RuntimeError(
                    "Instant-NGP Python interpreter could not be executed. "
                    "Set INSTANT_NGP_PYTHON to an absolute path or an executable available "
                    "in the current environment."
                )
            candidates.append(resolved)

        return candidates

    @staticmethod
    def _interpreter_can_import(interpreter: str, module_name: str) -> bool:
        try:
            completed = subprocess.run(
                [interpreter, "-c", f"import {module_name}"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return completed.returncode == 0
