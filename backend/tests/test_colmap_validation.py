"""Tests for COLMAP reconstruction validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.engines.camera_estimation.colmap_validation import (
    infer_mapper_failure_message,
    reconstruction_failure_message,
    registered_image_count,
)
from app.engines.camera_estimation.transforms_export import export_transforms_json


def test_infer_mapper_failure_message_detects_no_initial_pair() -> None:
    output = [
        "Finding good initial image pair",
        "=> No good initial image pair found.",
        "Discarding reconstruction due to no initial pair",
    ]
    message = infer_mapper_failure_message(output)
    assert message == (
        "COLMAP failed to produce a valid camera reconstruction: "
        "no good initial image pair found."
    )


def test_reconstruction_failure_message_prefers_mapper_reason() -> None:
    output = ["=> No good initial image pair found."]
    message = reconstruction_failure_message(mapper_output=output, registered_images=0)
    assert "no good initial image pair found" in message


def test_valid_sparse_reconstruction_exports_transforms(tmp_path: Path) -> None:
    cameras_txt = tmp_path / "cameras.txt"
    images_txt = tmp_path / "images.txt"
    output_path = tmp_path / "transforms.json"

    cameras_txt.write_text(
        "# Camera list\n1 OPENCV 640 480 800.0 800.0 320.0 240.0 0.0 0.0 0.0 0.0\n",
        encoding="utf-8",
    )
    images_txt.write_text(
        "# Image list\n"
        "1 1 0 0 0 0 0 0 1 image_a.png\n"
        "\n"
        "2 0.7071068 0 0.7071068 1 0 0 1 1 image_b.png\n"
        "\n",
        encoding="utf-8",
    )

    assert registered_image_count(images_txt) == 2
    document = export_transforms_json(
        cameras_txt=cameras_txt,
        images_txt=images_txt,
        output_path=output_path,
    )
    assert output_path.is_file()
    assert len(document["frames"]) == 2


def test_empty_images_txt_is_not_a_valid_reconstruction(tmp_path: Path) -> None:
    images_txt = tmp_path / "images.txt"
    images_txt.write_text("# Image list\n# Number of images: 0\n", encoding="utf-8")
    assert registered_image_count(images_txt) == 0

    message = reconstruction_failure_message(
        mapper_output=["=> No good initial image pair found."],
        registered_images=0,
    )
    assert "no good initial image pair found" in message
