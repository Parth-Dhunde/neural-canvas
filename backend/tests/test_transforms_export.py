"""Tests for COLMAP transforms export."""

from __future__ import annotations

import json
from pathlib import Path

from app.engines.camera_estimation.transforms_export import export_transforms_json


def test_export_transforms_json_writes_nerf_compatible_frames(tmp_path: Path) -> None:
    cameras_txt = tmp_path / "cameras.txt"
    images_txt = tmp_path / "images.txt"
    output_path = tmp_path / "transforms.json"

    cameras_txt.write_text(
        "# Camera list\n"
        "1 PINHOLE 640 480 800.0 800.0 320.0 240.0\n",
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

    document = export_transforms_json(
        cameras_txt=cameras_txt,
        images_txt=images_txt,
        output_path=output_path,
    )

    assert output_path.is_file()
    loaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert loaded["w"] == 640.0
    assert loaded["h"] == 480.0
    assert loaded["fl_x"] == 800.0
    assert len(loaded["frames"]) == 2
    assert loaded["frames"][0]["file_path"] == "../../masked_images/image_a.png"
    assert len(loaded["frames"][0]["transform_matrix"]) == 4
    assert document["frames"][1]["file_path"].endswith("image_b.png")
