"""Image upload handling for reconstruction jobs."""

from pathlib import Path

import aiofiles
from fastapi import UploadFile
from PIL import Image

from app.core.logging import get_logger
from app.jobs.repository import JobRepository
from app.jobs.structure import (
    PREVIEW_DIR,
    SUPPORTED_IMAGE_EXTENSIONS,
    UPLOADED_IMAGES_DIR,
    preview_path,
    uploaded_images_path,
)
from app.models.job import Job, utc_now_iso
from app.pipeline.pipeline_state import PipelineState

logger = get_logger(__name__)

THUMBNAIL_SIZE = (256, 256)
PREVIEW_SUFFIX = "_preview.jpg"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_UPLOAD_FILES = 100
MAX_IMAGE_PIXELS = 40_000_000


class UploadError(Exception):
    """Raised when an upload request is invalid."""


class UploadService:
    """Save uploaded images and generate preview thumbnails for a job."""

    def __init__(
        self,
        repository: JobRepository | None = None,
        pipeline_state: PipelineState | None = None,
    ) -> None:
        self._repository = repository or JobRepository()
        self._pipeline_state = pipeline_state or PipelineState()

    async def upload_images(self, job_id: str, files: list[UploadFile]) -> dict[str, object]:
        """Validate, store, and register uploaded images for a job."""
        if not files:
            raise UploadError("No files provided")
        if len(files) > MAX_UPLOAD_FILES:
            raise UploadError(
                f"Too many files in one upload (max {MAX_UPLOAD_FILES}). "
                "Upload in smaller batches."
            )

        job = self._repository.get(job_id)
        if job is None:
            raise UploadError(f"Job not found: {job_id}")

        uploads_dir = uploaded_images_path(self._repository.jobs_root, job_id)
        previews_dir = preview_path(self._repository.jobs_root, job_id)
        uploads_dir.mkdir(parents=True, exist_ok=True)
        previews_dir.mkdir(parents=True, exist_ok=True)

        saved_names: list[str] = []
        preview_names: list[str] = []

        for upload in files:
            if not upload.filename:
                raise UploadError("One or more files are missing a filename")

            original_name = Path(upload.filename).name
            extension = Path(original_name).suffix.lower()
            if extension not in SUPPORTED_IMAGE_EXTENSIONS:
                raise UploadError(
                    f"Unsupported format '{extension}'. Supported: jpg, jpeg, png"
                )

            content = await upload.read()
            if not content:
                raise UploadError(f"Empty file rejected: {original_name}")
            if len(content) > MAX_UPLOAD_BYTES:
                limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
                raise UploadError(
                    f"File too large: {original_name} (max {limit_mb} MB per image)"
                )

            safe_name = self._unique_filename(uploads_dir, original_name)
            destination = uploads_dir / safe_name

            async with aiofiles.open(destination, "wb") as handle:
                await handle.write(content)

            preview_name = self._generate_preview(destination, previews_dir)
            saved_names.append(safe_name)
            preview_names.append(preview_name)
            logger.info(
                "Saved upload | job_id=%s file=%s preview=%s",
                job_id,
                safe_name,
                preview_name,
            )

        existing = list(job.image_filenames)
        merged = existing + saved_names
        uploaded_at = utc_now_iso()

        updated = self._repository.update(
            job_id,
            image_count=len(merged),
            uploaded_at=uploaded_at,
            image_filenames=merged,
        )
        if updated is None:
            raise UploadError(f"Failed to update metadata for job: {job_id}")

        self._pipeline_state.mark_upload_complete(job_id, completed_at=uploaded_at)

        return {
            "job_id": job_id,
            "uploaded": saved_names,
            "image_count": len(merged),
            "uploaded_at": uploaded_at,
            "previews": preview_names,
            "job": updated,
        }

    @staticmethod
    def _unique_filename(directory: Path, filename: str) -> str:
        """Return a collision-free filename inside ``directory``."""
        candidate = Path(filename).name
        if not (directory / candidate).exists():
            return candidate

        stem = Path(candidate).stem
        suffix = Path(candidate).suffix
        index = 1
        while True:
            candidate = f"{stem}_{index}{suffix}"
            if not (directory / candidate).exists():
                return candidate
            index += 1

    @staticmethod
    def _generate_preview(source: Path, previews_dir: Path) -> str:
        """Create a JPEG thumbnail and return its filename."""
        preview_name = f"{source.stem}{PREVIEW_SUFFIX}"
        preview_file = previews_dir / preview_name

        with Image.open(source) as image:
            width, height = image.size
            if width * height > MAX_IMAGE_PIXELS:
                raise UploadError(
                    f"Image resolution too large: {source.name} "
                    f"({width}x{height}). Reduce resolution before uploading."
                )
            rgb = image.convert("RGB")
            rgb.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            rgb.save(preview_file, format="JPEG", quality=85)

        return preview_name

    @staticmethod
    def resolve_preview_file(jobs_root: Path, job_id: str, filename: str) -> Path:
        """Resolve and validate a preview file path."""
        safe_name = Path(filename).name
        target = preview_path(jobs_root, job_id) / safe_name
        if not target.is_file():
            raise FileNotFoundError(safe_name)
        if target.parent.name != PREVIEW_DIR:
            raise FileNotFoundError(safe_name)
        return target

    @staticmethod
    def list_previews(jobs_root: Path, job_id: str) -> list[str]:
        """Return preview filenames for a job."""
        directory = preview_path(jobs_root, job_id)
        if not directory.exists():
            return []
        return sorted(path.name for path in directory.glob(f"*{PREVIEW_SUFFIX}"))


def get_upload_service() -> UploadService:
    """FastAPI dependency that returns an upload service instance."""
    return UploadService()
