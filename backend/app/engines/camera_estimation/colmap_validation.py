"""Validation helpers for COLMAP sparse reconstruction outputs."""

from __future__ import annotations

from pathlib import Path

from app.engines.camera_estimation.transforms_export import parse_images_txt

MIN_REGISTERED_IMAGES = 2

MAPPER_FAILURE_SIGNATURES: tuple[tuple[str, str], ...] = (
    (
        "no good initial image pair found",
        "COLMAP failed to produce a valid camera reconstruction: no good initial image pair found.",
    ),
    (
        "discarding reconstruction due to no initial pair",
        "COLMAP failed to produce a valid camera reconstruction: no good initial image pair found.",
    ),
)


def infer_mapper_failure_message(output_lines: list[str]) -> str | None:
    """Return a user-facing failure message parsed from COLMAP mapper logs."""
    joined = "\n".join(line.lower() for line in output_lines)
    for signature, message in MAPPER_FAILURE_SIGNATURES:
        if signature in joined:
            return message
    return None


def sparse_model_has_files(model_dir: Path) -> bool:
    """Return True when a sparse model directory contains COLMAP model files."""
    has_binary = (model_dir / "cameras.bin").is_file() and (model_dir / "images.bin").is_file()
    has_text = (model_dir / "cameras.txt").is_file() and (model_dir / "images.txt").is_file()
    return has_binary or has_text


def sparse_model_is_usable(model_dir: Path, *, registered_images: int) -> bool:
    """Return True when a sparse model contains enough registered views."""
    if not sparse_model_has_files(model_dir):
        return False
    return registered_images >= MIN_REGISTERED_IMAGES


def registered_image_count(images_txt: Path) -> int:
    """Count registered images in a COLMAP ``images.txt`` file."""
    if not images_txt.is_file():
        return 0
    try:
        return len(parse_images_txt(images_txt))
    except (ValueError, IndexError):
        return 0


def registration_ratio_failure_message(
    *,
    registered_images: int,
    eligible_images: int,
    min_ratio: float,
) -> str | None:
    """Return a failure message when too few eligible images were registered."""
    if eligible_images <= 0:
        return None
    ratio = registered_images / eligible_images
    if ratio >= min_ratio:
        return None
    return (
        "COLMAP registered too few images for a reliable reconstruction: "
        f"{registered_images}/{eligible_images} eligible images ({ratio:.0%}), "
        f"minimum required is {min_ratio:.0%} (COLMAP_MIN_REGISTRATION_RATIO)."
    )


def reconstruction_failure_message(
    *,
    mapper_output: list[str],
    registered_images: int,
) -> str:
    """Build a failure message for an unusable COLMAP reconstruction."""
    mapper_message = infer_mapper_failure_message(mapper_output)
    if registered_images <= 0 and mapper_message is not None:
        return mapper_message
    if registered_images < MIN_REGISTERED_IMAGES:
        if mapper_message is not None:
            return mapper_message
        return (
            "COLMAP failed to produce a valid camera reconstruction: "
            f"only {registered_images} registered image(s) found."
        )
    return (
        "COLMAP failed to produce a valid camera reconstruction: "
        f"only {registered_images} registered image(s) found."
    )
