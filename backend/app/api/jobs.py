"""Job management HTTP routes."""

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.jobs.job_logs import MAX_PAGE_SIZE, get_job_log_store
from app.jobs.structure import (
    MASKED_IMAGES_DIR,
    SUPPORTED_IMAGE_EXTENSIONS,
    UPLOADED_IMAGES_DIR,
    camera_transforms_file,
    instant_ngp_snapshot_path,
    job_root_path,
    masked_images_path,
    uploaded_images_path,
)
from app.models.job import Job
from app.pipeline.pipeline_manager import (
    PipelineBusyError,
    PipelineManager,
    PipelineNotFoundError,
    get_pipeline_manager,
)
from app.schemas.job import (
    BackgroundRemovalResponse,
    JobCreateRequest,
    JobListResponse,
    JobResponse,
    UploadResponse,
)
from app.schemas.pipeline import (
    JobLogEntryResponse,
    JobLogsResponse,
    PipelineExecutionResponse,
    PipelineResponse,
    PipelineStageResponse,
    PipelineStartResponse,
)
from app.services.export_service import (
    MEDIA_TYPES,
    ExportError,
    ExportService,
    get_export_service,
)
from app.services.job_manager import JobManagerImpl, get_job_manager
from app.services.job_summary import summarize_job
from app.services.upload_service import UploadError, UploadService, get_upload_service

router = APIRouter(prefix="/jobs", tags=["jobs"])

ImageSource = Literal["original", "masked"]


def _to_response(job: Job, manager: JobManagerImpl) -> JobResponse:
    summary = summarize_job(job, manager.repository)
    return JobResponse(
        **summary,
        id=job.id,
        name=job.name,
        engine=job.engine,
        created_at=job.created_at,
        image_count=job.image_count,
        uploaded_at=job.uploaded_at,
        image_filenames=job.image_filenames,
        camera_estimated_at=job.camera_estimated_at,
        transforms_path=job.transforms_path,
        registered_image_count=job.registered_image_count,
        reconstruction_started_at=job.reconstruction_started_at,
        reconstruction_completed_at=job.reconstruction_completed_at,
        snapshot_path=job.snapshot_path,
        mesh_generated_at=job.mesh_generated_at,
        mesh_path=job.mesh_path,
        mesh_formats=job.mesh_formats,
        vertex_count=job.vertex_count,
        triangle_count=job.triangle_count,
        mesh_cleanup=job.mesh_cleanup,
        exports=job.exports,
    )


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreateRequest,
    manager: JobManagerImpl = Depends(get_job_manager),
) -> JobResponse:
    """Create a new reconstruction job and its on-disk workspace."""
    try:
        job = await manager.create_job(name=payload.name, engine=payload.engine)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _to_response(job, manager)


@router.get("", response_model=JobListResponse)
async def list_jobs(
    manager: JobManagerImpl = Depends(get_job_manager),
) -> JobListResponse:
    """Return all jobs stored on disk."""
    jobs = await manager.list_jobs()
    responses = [_to_response(job, manager) for job in jobs]
    return JobListResponse(jobs=responses, total=len(responses))


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    manager: JobManagerImpl = Depends(get_job_manager),
) -> JobResponse:
    """Return a single job by identifier."""
    job = await manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")
    return _to_response(job, manager)


@router.post("/{job_id}/upload", response_model=UploadResponse)
async def upload_job_images(
    job_id: str,
    files: list[UploadFile] = File(...),
    upload_service: UploadService = Depends(get_upload_service),
) -> UploadResponse:
    """Upload one or more images to a job workspace."""
    try:
        result = await upload_service.upload_images(job_id, files)
    except UploadError as exc:
        message = str(exc)
        code = status.HTTP_404_NOT_FOUND if "not found" in message.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=message) from exc

    return UploadResponse(
        job_id=str(result["job_id"]),
        uploaded=list(result["uploaded"]),
        image_count=int(result["image_count"]),
        uploaded_at=str(result["uploaded_at"]),
        previews=list(result["previews"]),
    )


@router.get("/{job_id}/preview/{filename}")
async def get_job_preview(
    job_id: str,
    filename: str,
    manager: JobManagerImpl = Depends(get_job_manager),
) -> FileResponse:
    """Serve a generated preview thumbnail for a job."""
    job = await manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")

    repository = manager.repository
    try:
        preview_file = UploadService.resolve_preview_file(
            repository.jobs_root,
            job_id,
            filename,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return FileResponse(path=Path(preview_file), media_type="image/jpeg")


def _count_masked_images(jobs_root: Path, job_id: str) -> int:
    directory = masked_images_path(jobs_root, job_id)
    if not directory.is_dir():
        return 0
    return sum(
        1
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    )


def _pipeline_response(
    manager: JobManagerImpl,
    job: Job,
    pipeline_manager: PipelineManager,
) -> PipelineResponse:
    repository = manager.repository
    masked_count = _count_masked_images(repository.jobs_root, job.id)
    has_transforms = camera_transforms_file(repository.jobs_root, job.id).is_file()
    has_snapshot = instant_ngp_snapshot_path(repository.jobs_root, job.id).is_file()
    document = pipeline_manager.reconcile_with_job(
        job.id,
        image_count=job.image_count,
        uploaded_at=job.uploaded_at,
        masked_image_count=masked_count,
        has_transforms=has_transforms,
        camera_estimated_at=job.camera_estimated_at,
        has_snapshot=has_snapshot,
        reconstruction_completed_at=job.reconstruction_completed_at,
    )
    stages = [PipelineStageResponse(**stage) for stage in document["stages"]]
    execution = document.get("execution") or {}
    return PipelineResponse(
        stages=stages,
        execution=PipelineExecutionResponse(
            status=str(execution.get("status", "idle")),
            current_stage_id=execution.get("current_stage_id"),
            last_error=execution.get("last_error"),
        ),
    )


def _start_response(job_id: str, result) -> PipelineStartResponse:
    data = result.last_result.data if result.last_result else {}
    return PipelineStartResponse(
        job_id=job_id,
        stages_run=result.stages_run,
        logs=result.logs,
        stopped_reason=result.stopped_reason,
        processed=data.get("processed"),
        failed=data.get("failed"),
        total=data.get("total"),
    )


@router.get("/{job_id}/pipeline", response_model=PipelineResponse)
async def get_job_pipeline(
    job_id: str,
    manager: JobManagerImpl = Depends(get_job_manager),
    pipeline_manager: PipelineManager = Depends(get_pipeline_manager),
) -> PipelineResponse:
    """Return persisted pipeline state for a job."""
    job = await manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")
    return _pipeline_response(manager, job, pipeline_manager)


@router.get("/{job_id}/logs", response_model=JobLogsResponse)
async def get_job_logs(
    job_id: str,
    after: int = Query(default=0, ge=0, description="Return entries with seq greater than this."),
    limit: int = Query(default=500, ge=1, le=MAX_PAGE_SIZE),
    tail: int | None = Query(
        default=None, ge=1, le=MAX_PAGE_SIZE, description="Return only the last N entries."
    ),
    manager: JobManagerImpl = Depends(get_job_manager),
) -> JobLogsResponse:
    """Return pipeline log entries incrementally for polling clients."""
    job = await manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")

    page = get_job_log_store(manager.repository.jobs_root).read(
        job_id, after=after, limit=limit, tail=tail
    )
    return JobLogsResponse(
        job_id=job_id,
        entries=[JobLogEntryResponse(**entry.to_dict()) for entry in page.entries],
        next_after=page.next_after,
        last_seq=page.last_seq,
        has_more=page.has_more,
        truncated=page.truncated,
        reset=page.reset,
    )


@router.post("/{job_id}/pipeline/start", response_model=PipelineStartResponse)
async def start_job_pipeline(
    job_id: str,
    manager: JobManagerImpl = Depends(get_job_manager),
    pipeline_manager: PipelineManager = Depends(get_pipeline_manager),
) -> PipelineStartResponse:
    """Run the reconstruction pipeline from the next incomplete stage."""
    job = await manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")

    try:
        result = await pipeline_manager.run_pipeline(job_id)
    except PipelineNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PipelineBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return _start_response(job_id, result)


@router.post("/{job_id}/pipeline/stages/{stage_id}/run", response_model=PipelineStartResponse)
async def run_job_pipeline_stage(
    job_id: str,
    stage_id: int,
    manager: JobManagerImpl = Depends(get_job_manager),
    pipeline_manager: PipelineManager = Depends(get_pipeline_manager),
) -> PipelineStartResponse:
    """Run a single pipeline stage."""
    job = await manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")

    try:
        result = await pipeline_manager.run_stage(job_id, stage_id)
    except PipelineNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PipelineBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return _start_response(job_id, result)


@router.post("/{job_id}/pipeline/stages/{stage_id}/reset", response_model=PipelineResponse)
async def reset_job_pipeline_stage(
    job_id: str,
    stage_id: int,
    manager: JobManagerImpl = Depends(get_job_manager),
    pipeline_manager: PipelineManager = Depends(get_pipeline_manager),
) -> PipelineResponse:
    """Reset a stage and all later stages to waiting. Does not run anything or delete files."""
    job = await manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")

    try:
        await pipeline_manager.reset_from_stage(job_id, stage_id)
    except PipelineNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PipelineBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return _pipeline_response(manager, job, pipeline_manager)


@router.post("/{job_id}/pipeline/pause", response_model=PipelineResponse)
async def pause_job_pipeline(
    job_id: str,
    manager: JobManagerImpl = Depends(get_job_manager),
    pipeline_manager: PipelineManager = Depends(get_pipeline_manager),
) -> PipelineResponse:
    """Pause an in-flight pipeline."""
    job = await manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")

    pipeline_manager.pause(job_id)
    return _pipeline_response(manager, job, pipeline_manager)


@router.post("/{job_id}/pipeline/resume", response_model=PipelineStartResponse)
async def resume_job_pipeline(
    job_id: str,
    manager: JobManagerImpl = Depends(get_job_manager),
    pipeline_manager: PipelineManager = Depends(get_pipeline_manager),
) -> PipelineStartResponse:
    """Resume a paused pipeline."""
    job = await manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")

    pipeline_manager.resume(job_id)
    try:
        result = await pipeline_manager.run_pipeline(job_id)
    except PipelineNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PipelineBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return _start_response(job_id, result)


@router.post("/{job_id}/pipeline/cancel", response_model=PipelineResponse)
async def cancel_job_pipeline(
    job_id: str,
    manager: JobManagerImpl = Depends(get_job_manager),
    pipeline_manager: PipelineManager = Depends(get_pipeline_manager),
) -> PipelineResponse:
    """Cancel an in-flight pipeline."""
    job = await manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")

    pipeline_manager.cancel(job_id)
    return _pipeline_response(manager, job, pipeline_manager)


@router.post("/{job_id}/pipeline/recover", response_model=PipelineResponse)
async def recover_job_pipeline(
    job_id: str,
    manager: JobManagerImpl = Depends(get_job_manager),
    pipeline_manager: PipelineManager = Depends(get_pipeline_manager),
) -> PipelineResponse:
    """Recover pipeline state after a backend restart."""
    job = await manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")

    pipeline_manager.recover(job_id)
    return _pipeline_response(manager, job, pipeline_manager)


@router.post("/{job_id}/background-removal", response_model=BackgroundRemovalResponse)
async def run_background_removal(
    job_id: str,
    manager: JobManagerImpl = Depends(get_job_manager),
    pipeline_manager: PipelineManager = Depends(get_pipeline_manager),
) -> BackgroundRemovalResponse:
    """Run background removal on uploaded images for a job."""
    job = await manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")

    try:
        result = await pipeline_manager.run_stage(job_id, 2)
    except PipelineNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PipelineBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    stage_data = result.last_result.data if result.last_result else {}
    if result.stopped_reason == "stage_failed":
        message = result.last_result.message if result.last_result else "Stage failed"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    return BackgroundRemovalResponse(
        job_id=job_id,
        processed=int(stage_data.get("processed", 0)),
        failed=int(stage_data.get("failed", 0)),
        total=int(stage_data.get("total", 0)),
        logs=result.logs,
    )


@router.get("/{job_id}/images/{source}/{filename}")
async def get_job_image(
    job_id: str,
    source: ImageSource,
    filename: str,
    manager: JobManagerImpl = Depends(get_job_manager),
) -> FileResponse:
    """Serve an original or masked image for a job."""
    job = await manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")

    safe_name = Path(filename).name
    repository = manager.repository

    if source == "original":
        target = uploaded_images_path(repository.jobs_root, job_id) / safe_name
        expected_parent = UPLOADED_IMAGES_DIR
    else:
        target = masked_images_path(repository.jobs_root, job_id) / safe_name
        expected_parent = MASKED_IMAGES_DIR

    if not target.is_file() or target.parent.name != expected_parent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image not found: {safe_name}",
        )

    media_type = "image/png" if safe_name.lower().endswith(".png") else "image/jpeg"
    return FileResponse(path=target, media_type=media_type)


@router.get("/{job_id}/mesh")
async def get_job_mesh(
    job_id: str,
    manager: JobManagerImpl = Depends(get_job_manager),
) -> FileResponse:
    """Stream the latest generated mesh (GLB) for a job."""
    job = await manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")

    if not job.mesh_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No mesh exists for this job.")

    root = job_root_path(manager.repository.jobs_root, job_id)
    candidate = (root / Path(job.mesh_path)).resolve()
    if root.resolve() not in candidate.parents and candidate != root.resolve():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid mesh path.")

    if not candidate.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No mesh exists for this job.")

    return FileResponse(path=candidate, media_type="model/gltf-binary", filename="mesh.glb")


@router.get("/{job_id}/exports")
async def get_job_exports(
    job_id: str,
    exports: ExportService = Depends(get_export_service),
) -> dict[str, object]:
    """List cleaned and original mesh downloads, verified against the files on disk.

    ``preferred`` is "cleaned" only when Stage 6 succeeded for the current Stage 5 mesh and its
    GLB verifies; otherwise the original Stage 5 GLB (or null when there is no mesh).
    """
    try:
        job = exports.require_job(job_id)
    except ExportError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return exports.manifest(job)


@router.get("/{job_id}/exports/{variant}/{fmt}")
async def download_job_export(
    job_id: str,
    variant: Literal["cleaned", "original"],
    fmt: Literal["glb", "obj", "ply"],
    exports: ExportService = Depends(get_export_service),
) -> FileResponse:
    """Download a verified mesh file. Paths are resolved only inside the job directory."""
    try:
        job = exports.require_job(job_id)
        path = exports.resolve_download(job, variant, fmt)
    except ExportError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FileResponse(
        path=path,
        media_type=MEDIA_TYPES[fmt],
        filename=f"{job_id}_{variant}.{fmt}",
    )
