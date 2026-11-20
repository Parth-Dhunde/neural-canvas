"""Expected on-disk layout for a reconstruction job."""

from pathlib import Path

JOB_ID_PREFIX = "job_"

JOB_SUBDIRECTORIES: tuple[str, ...] = (
    "uploaded_images",
    "masked_images",
    "camera",
    "instant_ngp",
    "meshes",
    "exports",
    "logs",
    "preview",
)

UPLOADED_IMAGES_DIR = "uploaded_images"
MASKED_IMAGES_DIR = "masked_images"
CAMERA_DIR = "camera"
CAMERA_DATABASE_FILE = "database.db"
CAMERA_SPARSE_DIR = "sparse"
CAMERA_TRANSFORMS_DIR = "transforms"
CAMERA_TRANSFORMS_FILE = "transforms.json"
INSTANT_NGP_DIR = "instant_ngp"
INSTANT_NGP_SNAPSHOT_FILE = "snapshot.msgpack"
INSTANT_NGP_TRAINING_LOG_FILE = "training.log"
INSTANT_NGP_CHECKPOINTS_DIR = "checkpoints"
PREVIEW_DIR = "preview"
MESHES_DIR = "meshes"
MESH_OBJ_FILE = "mesh.obj"
MESH_PLY_FILE = "mesh.ply"
MESH_GLB_FILE = "mesh.glb"
MESH_CLEANUP_DIR = "cleanup"
MESH_CLEANUP_REPORT_FILE = "cleanup.json"
EXPORTS_DIR = "exports"
EXPORT_MANIFEST_FILE = "manifest.json"
MESH_FORMATS: tuple[str, ...] = ("ply", "obj", "glb")

JOB_LOGS_DIR = "logs"
PIPELINE_LOG_FILE = "pipeline.jsonl"

JOB_METADATA_FILE = "metadata.json"
JOB_REPORT_FILE = "report.json"
JOB_PIPELINE_FILE = "pipeline.json"

SUPPORTED_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png"})


def job_directory_name(job_id: str) -> str:
    """Return the canonical directory name for a job identifier."""
    if job_id.startswith(JOB_ID_PREFIX):
        return job_id
    return f"{JOB_ID_PREFIX}{job_id}"


def job_root_path(jobs_root: Path, job_id: str) -> Path:
    """Return the absolute path to a job's root directory."""
    return jobs_root / job_directory_name(job_id)


def uploaded_images_path(jobs_root: Path, job_id: str) -> Path:
    """Return the absolute path to a job's uploaded images directory."""
    return job_root_path(jobs_root, job_id) / UPLOADED_IMAGES_DIR


def preview_path(jobs_root: Path, job_id: str) -> Path:
    """Return the absolute path to a job's preview thumbnails directory."""
    return job_root_path(jobs_root, job_id) / PREVIEW_DIR


def masked_images_path(jobs_root: Path, job_id: str) -> Path:
    """Return the absolute path to a job's masked images directory."""
    return job_root_path(jobs_root, job_id) / MASKED_IMAGES_DIR


def camera_path(jobs_root: Path, job_id: str) -> Path:
    """Return the absolute path to a job's camera estimation directory."""
    return job_root_path(jobs_root, job_id) / CAMERA_DIR


def camera_database_path(jobs_root: Path, job_id: str) -> Path:
    """Return the absolute path to the COLMAP database for a job."""
    return camera_path(jobs_root, job_id) / CAMERA_DATABASE_FILE


def camera_sparse_path(jobs_root: Path, job_id: str) -> Path:
    """Return the absolute path to the COLMAP sparse reconstruction directory."""
    return camera_path(jobs_root, job_id) / CAMERA_SPARSE_DIR


def camera_transforms_path(jobs_root: Path, job_id: str) -> Path:
    """Return the absolute path to the transforms output directory."""
    return camera_path(jobs_root, job_id) / CAMERA_TRANSFORMS_DIR


def camera_transforms_file(jobs_root: Path, job_id: str) -> Path:
    """Return the absolute path to ``transforms.json`` for a job."""
    return camera_transforms_path(jobs_root, job_id) / CAMERA_TRANSFORMS_FILE


def camera_transforms_relative_path() -> str:
    """Return the job-relative path to ``transforms.json``."""
    return f"{CAMERA_DIR}/{CAMERA_TRANSFORMS_DIR}/{CAMERA_TRANSFORMS_FILE}"


def instant_ngp_output_path(jobs_root: Path, job_id: str) -> Path:
    """Return the absolute path to a job's Instant-NGP output directory."""
    return job_root_path(jobs_root, job_id) / INSTANT_NGP_DIR


def instant_ngp_snapshot_path(jobs_root: Path, job_id: str) -> Path:
    """Return the absolute path to the Instant-NGP snapshot file."""
    return instant_ngp_output_path(jobs_root, job_id) / INSTANT_NGP_SNAPSHOT_FILE


def instant_ngp_training_log_path(jobs_root: Path, job_id: str) -> Path:
    """Return the absolute path to the Instant-NGP training log."""
    return instant_ngp_output_path(jobs_root, job_id) / INSTANT_NGP_TRAINING_LOG_FILE


def instant_ngp_checkpoints_path(jobs_root: Path, job_id: str) -> Path:
    """Return the absolute path to the Instant-NGP checkpoints directory."""
    return instant_ngp_output_path(jobs_root, job_id) / INSTANT_NGP_CHECKPOINTS_DIR


def instant_ngp_snapshot_relative_path() -> str:
    """Return the job-relative path to ``snapshot.msgpack``."""
    return f"{INSTANT_NGP_DIR}/{INSTANT_NGP_SNAPSHOT_FILE}"


def meshes_path(jobs_root: Path, job_id: str) -> Path:
    """Return the absolute path to a job's mesh output directory."""
    return job_root_path(jobs_root, job_id) / MESHES_DIR


def pipeline_log_path(jobs_root: Path, job_id: str) -> Path:
    """Return the absolute path to the persistent pipeline log for a job."""
    return job_root_path(jobs_root, job_id) / JOB_LOGS_DIR / PIPELINE_LOG_FILE
