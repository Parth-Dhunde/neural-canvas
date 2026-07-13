"""Background removal orchestration for reconstruction jobs."""

import asyncio
from collections.abc import Callable
from pathlib import Path

from app.core.logging import get_logger
from app.engines.background_removal.base import BackgroundRemovalEngine
from app.engines.background_removal import get_background_removal_engine
from app.jobs.repository import JobRepository
from app.jobs.structure import (
    SUPPORTED_IMAGE_EXTENSIONS,
    masked_images_path,
    uploaded_images_path,
)

logger = get_logger(__name__)


class BackgroundRemovalError(Exception):
    """Raised when background removal cannot start."""


class BackgroundRemovalService:
    """Run background removal for a job using a pluggable engine."""

    def __init__(
        self,
        repository: JobRepository | None = None,
        engine: BackgroundRemovalEngine | None = None,
    ) -> None:
        self._repository = repository or JobRepository()
        self._engine = engine or get_background_removal_engine()

    async def run(self, job_id: str) -> dict[str, object]:
        """Process all uploaded images and write masked outputs."""
        return await self.process_images(job_id)

    async def process_images(
        self,
        job_id: str,
        *,
        log: Callable[[str, str], None] | Callable[[str], None] | None = None,
        on_progress: Callable[[int], None] | None = None,
        check_control: Callable[[], None] | None = None,
    ) -> dict[str, object]:
        """Process uploaded images without updating pipeline state."""
        job = self._repository.get(job_id)
        if job is None:
            raise BackgroundRemovalError(f"Job not found: {job_id}")

        uploads_dir = uploaded_images_path(self._repository.jobs_root, job_id)
        masked_dir = masked_images_path(self._repository.jobs_root, job_id)
        masked_dir.mkdir(parents=True, exist_ok=True)

        sources = self._collect_source_images(uploads_dir, job.image_filenames)
        if not sources:
            raise BackgroundRemovalError("No uploaded images found for this job")

        total = len(sources)
        processed = 0
        failed = 0

        def emit(message: str, level: str = "info") -> None:
            if log is None:
                return
            try:
                log(message, level)
            except TypeError:
                log(message)

        for index, source in enumerate(sources, start=1):
            if check_control is not None:
                check_control()

            destination = masked_dir / source.name
            emit(f"Image {index}/{total}")

            try:
                await asyncio.to_thread(
                    self._engine.remove_background,
                    source,
                    destination,
                )
                processed += 1
            except Exception as exc:
                failed += 1
                emit(f"Failed: {source.name} — {exc}", level="error")
                logger.exception(
                    "Background removal failed | job_id=%s file=%s",
                    job_id,
                    source.name,
                )

            if on_progress is not None:
                on_progress(round((index / total) * 100))

        return {
            "job_id": job_id,
            "processed": processed,
            "failed": failed,
            "total": total,
        }

    @staticmethod
    def _collect_source_images(
        uploads_dir: Path,
        filenames: list[str],
    ) -> list[Path]:
        """Return sorted source image paths from disk."""
        if not uploads_dir.is_dir():
            return []

        discovered = sorted(
            path
            for path in uploads_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        )
        if discovered:
            return discovered

        return sorted(
            uploads_dir / name
            for name in filenames
            if (uploads_dir / name).is_file()
        )


def get_background_removal_service() -> BackgroundRemovalService:
    """FastAPI dependency that returns a background removal service instance."""
    return BackgroundRemovalService()
