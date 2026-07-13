"""Domain model for a reconstruction job."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    """In-memory representation of a reconstruction job."""

    id: str
    name: str
    engine: str
    status: str = "waiting"
    progress: int = 0
    created_at: str = field(default_factory=utc_now_iso)
    image_count: int = 0
    uploaded_at: str | None = None
    image_filenames: list[str] = field(default_factory=list)
    camera_estimated_at: str | None = None
    transforms_path: str | None = None
    registered_image_count: int = 0
    reconstruction_started_at: str | None = None
    reconstruction_completed_at: str | None = None
    snapshot_path: str | None = None
    mesh_generated_at: str | None = None
    mesh_path: str | None = None
    mesh_formats: list[str] = field(default_factory=list)
    vertex_count: int = 0
    triangle_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize the job to a plain dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Job":
        """Deserialize a job from a metadata dictionary."""
        filenames = data.get("image_filenames", [])
        return cls(
            id=data["id"],
            name=data["name"],
            engine=data["engine"],
            status=data.get("status", "waiting"),
            progress=int(data.get("progress", 0)),
            created_at=data.get("created_at", utc_now_iso()),
            image_count=int(data.get("image_count", 0)),
            uploaded_at=data.get("uploaded_at"),
            image_filenames=list(filenames) if filenames else [],
            camera_estimated_at=data.get("camera_estimated_at"),
            transforms_path=data.get("transforms_path"),
            registered_image_count=int(data.get("registered_image_count", 0)),
            reconstruction_started_at=data.get("reconstruction_started_at"),
            reconstruction_completed_at=data.get("reconstruction_completed_at"),
            snapshot_path=data.get("snapshot_path"),
            mesh_generated_at=data.get("mesh_generated_at"),
            mesh_path=data.get("mesh_path"),
            mesh_formats=list(data.get("mesh_formats") or []),
            vertex_count=int(data.get("vertex_count", 0)),
            triangle_count=int(data.get("triangle_count", 0)),
        )
