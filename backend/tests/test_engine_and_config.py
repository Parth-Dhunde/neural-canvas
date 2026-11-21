"""Only Instant-NGP jobs are accepted; the config endpoint exposes parameters, not host paths."""

from __future__ import annotations

import asyncio
import json

import pytest

from app.api.system import get_pipeline_config
from app.jobs.repository import JobRepository


@pytest.mark.parametrize("engine", ["Text-to-3D", "text-to-3d", "", "Shap-E"])
def test_non_instant_ngp_engines_are_rejected(engine: str) -> None:
    with pytest.raises(ValueError):
        JobRepository.validate_engine(engine)


def test_instant_ngp_is_accepted() -> None:
    assert JobRepository.validate_engine("Instant-NGP") == "Instant-NGP"


def test_pipeline_config_has_no_paths_or_binaries() -> None:
    payload = asyncio.run(get_pipeline_config())
    text = json.dumps(payload)
    assert "/" not in text.replace("backend/.env", "")
    assert "colmap_binary" not in text and "instant_ngp_root" not in text
    assert payload["training"]["n_steps"] > 0
    assert payload["export_formats"] == ["glb", "obj", "ply"]
