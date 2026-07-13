"""Tests for reconstruction engine factory and validation."""

from __future__ import annotations

from app.engines.reconstruction.factory import get_reconstruction_engine, normalize_engine_name
from app.models.job import Job


def test_normalize_engine_name_aliases() -> None:
    assert normalize_engine_name("instant-ngp") == "Instant-NGP"
    assert normalize_engine_name("custom_nerf") == "Custom NeRF"


def test_get_reconstruction_engine_for_instant_ngp() -> None:
    job = Job(id="job_000001", name="job_000001", engine="Instant-NGP")
    engine = get_reconstruction_engine(job)
    assert engine.name == "instant-ngp"


def test_get_reconstruction_engine_for_custom_nerf() -> None:
    job = Job(id="job_000001", name="job_000001", engine="Custom NeRF")
    engine = get_reconstruction_engine(job)
    assert engine.name == "custom-nerf"
