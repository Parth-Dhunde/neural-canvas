"""Tests for reconstruction engine factory and validation."""

from __future__ import annotations

import pytest

from app.engines.reconstruction.factory import get_reconstruction_engine, normalize_engine_name
from app.models.job import Job


def test_normalize_engine_name_aliases() -> None:
    assert normalize_engine_name("instant-ngp") == "Instant-NGP"
    assert normalize_engine_name("instant_ngp") == "Instant-NGP"


def test_get_reconstruction_engine_for_instant_ngp() -> None:
    job = Job(id="job_000001", name="job_000001", engine="Instant-NGP")
    engine = get_reconstruction_engine(job)
    assert engine.name == "instant-ngp"


def test_get_reconstruction_engine_rejects_unsupported_engine() -> None:
    job = Job(id="job_000001", name="job_000001", engine="Legacy Engine")
    with pytest.raises(ValueError, match="Unsupported reconstruction engine"):
        get_reconstruction_engine(job)
