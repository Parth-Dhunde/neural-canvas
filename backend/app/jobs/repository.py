"""Filesystem-backed persistence for reconstruction jobs."""

import json
import os
import re
import threading
from pathlib import Path

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.jobs.structure import (
    JOB_ID_PREFIX,
    JOB_METADATA_FILE,
    JOB_REPORT_FILE,
    JOB_SUBDIRECTORIES,
    job_directory_name,
    job_root_path,
)
from app.models.job import Job

logger = get_logger(__name__)

JOB_ID_PATTERN = re.compile(r"^job_(\d{6})$")
SUPPORTED_ENGINES = frozenset({"Instant-NGP"})


class JobRepository:
    """Read and write jobs under the configured jobs root directory."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def jobs_root(self) -> Path:
        """Absolute path to the jobs workspace root."""
        return self._settings.jobs_path

    def ensure_jobs_root(self) -> Path:
        """Create the jobs root directory if it does not exist."""
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        return self.jobs_root

    def next_job_id(self) -> str:
        """Generate the next sequential job identifier."""
        self.ensure_jobs_root()
        highest = 0
        for path in self.jobs_root.iterdir():
            if not path.is_dir():
                continue
            match = JOB_ID_PATTERN.match(path.name)
            if match:
                highest = max(highest, int(match.group(1)))
        return f"{JOB_ID_PREFIX}{highest + 1:06d}"

    def create_folder_structure(self, job_id: str) -> Path:
        """Create the on-disk directory layout for a job."""
        root = job_root_path(self.ensure_jobs_root(), job_id)
        root.mkdir(parents=True, exist_ok=False)

        for subdir in JOB_SUBDIRECTORIES:
            (root / subdir).mkdir(parents=True, exist_ok=True)

        report_path = root / JOB_REPORT_FILE
        if not report_path.exists():
            report_path.write_text(
                json.dumps({"job_id": job_id, "stages": []}, indent=2),
                encoding="utf-8",
            )

        logger.info("Created job workspace | job_id=%s path=%s", job_id, root)
        return root

    def save(self, job: Job) -> Job:
        """Persist job metadata to ``metadata.json``."""
        root = job_root_path(self.ensure_jobs_root(), job.id)
        metadata_path = root / JOB_METADATA_FILE
        # Write-then-rename so API polling never reads a partially written file.
        temp_path = metadata_path.with_name(
            f".{metadata_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        temp_path.write_text(json.dumps(job.to_dict(), indent=2), encoding="utf-8")
        os.replace(temp_path, metadata_path)
        return job

    def get(self, job_id: str) -> Job | None:
        """Load a single job by identifier."""
        root = job_root_path(self.jobs_root, job_id)
        metadata_path = root / JOB_METADATA_FILE
        if not metadata_path.is_file():
            return None
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
        return Job.from_dict(data)

    def list_all(self) -> list[Job]:
        """Return all jobs discovered on disk, newest first."""
        if not self.jobs_root.exists():
            return []

        jobs: list[Job] = []
        for path in self.jobs_root.iterdir():
            if not path.is_dir():
                continue
            if not JOB_ID_PATTERN.match(path.name):
                continue
            job = self.get(path.name)
            if job is not None:
                jobs.append(job)

        jobs.sort(key=lambda job: job.created_at, reverse=True)
        return jobs

    def update(self, job_id: str, **fields: object) -> Job | None:
        """Update persisted metadata fields for a job."""
        job = self.get(job_id)
        if job is None:
            return None

        data = job.to_dict()
        data.update(fields)
        updated = Job.from_dict(data)
        return self.save(updated)

    @staticmethod
    def validate_engine(engine: str) -> str:
        """Validate and return a supported engine identifier."""
        if engine not in SUPPORTED_ENGINES:
            supported = ", ".join(sorted(SUPPORTED_ENGINES))
            raise ValueError(f"Unsupported engine '{engine}'. Supported: {supported}")
        return engine

    @staticmethod
    def default_job_name(job_id: str) -> str:
        """Return the default display name for a job."""
        return job_directory_name(job_id)
