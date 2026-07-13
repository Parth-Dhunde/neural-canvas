"""Convert COLMAP sparse models to NeRF-compatible ``transforms.json``."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def qvec_to_rotmat(qw: float, qx: float, qy: float, qz: float) -> list[list[float]]:
    """Convert a COLMAP quaternion to a 3x3 rotation matrix."""
    norm = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
    if norm == 0:
        raise ValueError("Invalid zero-length quaternion")
    qw, qx, qy, qz = qw / norm, qx / norm, qy / norm, qz / norm
    return [
        [
            1 - 2 * qy * qy - 2 * qz * qz,
            2 * qx * qy - 2 * qz * qw,
            2 * qx * qz + 2 * qy * qw,
        ],
        [
            2 * qx * qy + 2 * qz * qw,
            1 - 2 * qx * qx - 2 * qz * qz,
            2 * qy * qz - 2 * qx * qw,
        ],
        [
            2 * qx * qz - 2 * qy * qw,
            2 * qy * qz + 2 * qx * qw,
            1 - 2 * qx * qx - 2 * qy * qy,
        ],
    ]


def invert_rigid(rotation: list[list[float]], translation: list[float]) -> list[list[float]]:
    """Invert a world-to-camera rigid transform and return a 4x4 camera-to-world matrix."""
    rt = [
        [rotation[0][0], rotation[1][0], rotation[2][0]],
        [rotation[0][1], rotation[1][1], rotation[2][1]],
        [rotation[0][2], rotation[1][2], rotation[2][2]],
    ]
    t_inv = [
        -(rt[0][0] * translation[0] + rt[0][1] * translation[1] + rt[0][2] * translation[2]),
        -(rt[1][0] * translation[0] + rt[1][1] * translation[1] + rt[1][2] * translation[2]),
        -(rt[2][0] * translation[0] + rt[2][1] * translation[1] + rt[2][2] * translation[2]),
    ]
    c2w = [
        [rt[0][0], rt[0][1], rt[0][2], t_inv[0]],
        [rt[1][0], rt[1][1], rt[1][2], t_inv[1]],
        [rt[2][0], rt[2][1], rt[2][2], t_inv[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]
    return c2w


def nerf_transform_matrix(c2w: list[list[float]]) -> list[list[float]]:
    """Convert a COLMAP camera-to-world matrix to the NeRF / Instant-NGP convention."""
    flip = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, -1.0, 0.0, 0.0],
        [0.0, 0.0, -1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    result = [[0.0] * 4 for _ in range(4)]
    for row in range(4):
        for col in range(4):
            result[row][col] = sum(c2w[row][k] * flip[k][col] for k in range(4))
    return result


def parse_cameras_txt(path: Path) -> dict[int, dict[str, Any]]:
    """Parse COLMAP ``cameras.txt`` into a camera-id mapping."""
    cameras: dict[int, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        camera_id = int(parts[0])
        model = parts[1]
        width = int(parts[2])
        height = int(parts[3])
        params = [float(value) for value in parts[4:]]
        cameras[camera_id] = {
            "model": model,
            "width": width,
            "height": height,
            "params": params,
        }
    return cameras


def parse_images_txt(path: Path) -> list[dict[str, Any]]:
    """Parse COLMAP ``images.txt`` into registered image records."""
    lines = path.read_text(encoding="utf-8").splitlines()
    images: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        index += 1
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        image_id = int(parts[0])
        qw, qx, qy, qz = (float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4]))
        tx, ty, tz = (float(parts[5]), float(parts[6]), float(parts[7]))
        camera_id = int(parts[8])
        name = " ".join(parts[9:])
        images.append(
            {
                "image_id": image_id,
                "qvec": (qw, qx, qy, qz),
                "tvec": (tx, ty, tz),
                "camera_id": camera_id,
                "name": name,
            }
        )
        if index < len(lines):
            index += 1
    return images


def intrinsics_from_camera(camera: dict[str, Any]) -> dict[str, float]:
    """Extract shared pinhole intrinsics from a COLMAP camera record."""
    model = camera["model"].upper()
    params = camera["params"]
    width = int(camera["width"])
    height = int(camera["height"])

    if model in {"SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL"}:
        fx = fy = params[0]
        cx = params[1]
        cy = params[2]
    elif model in {"PINHOLE", "OPENCV", "FULL_OPENCV", "SIMPLE_RADIAL_FISHEYE", "RADIAL_FISHEYE", "OPENCV_FISHEYE"}:
        fx = params[0]
        fy = params[1]
        cx = params[2]
        cy = params[3]
    else:
        raise ValueError(f"Unsupported COLMAP camera model: {model}")

    return {
        "camera_model": "OPENCV" if model == "OPENCV" else "PINHOLE",
        "fl_x": fx,
        "fl_y": fy,
        "cx": cx,
        "cy": cy,
        "w": float(width),
        "h": float(height),
    }


def relative_masked_image_path(image_name: str) -> str:
    """Return a transforms-relative path to a masked source image."""
    return f"../../{Path('masked_images') / Path(image_name).name}".replace("\\", "/")


def export_transforms_json(
    *,
    cameras_txt: Path,
    images_txt: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Write a NeRF-compatible ``transforms.json`` document."""
    cameras = parse_cameras_txt(cameras_txt)
    images = parse_images_txt(images_txt)
    if not images:
        raise ValueError("COLMAP reconstruction contains no registered images")

    primary_camera = cameras[images[0]["camera_id"]]
    intrinsics = intrinsics_from_camera(primary_camera)

    frames: list[dict[str, Any]] = []
    for image in sorted(images, key=lambda item: item["image_id"]):
        qw, qx, qy, qz = image["qvec"]
        tx, ty, tz = image["tvec"]
        rotation = qvec_to_rotmat(qw, qx, qy, qz)
        c2w = invert_rigid(rotation, [tx, ty, tz])
        frames.append(
            {
                "file_path": relative_masked_image_path(image["name"]),
                "transform_matrix": nerf_transform_matrix(c2w),
            }
        )

    document: dict[str, Any] = {
        **intrinsics,
        "aabb_scale": 4,
        "frames": frames,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return document
