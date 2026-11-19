"""Tests for local hardware introspection."""

from __future__ import annotations

from app.services.hardware_info import collect_hardware_summary


def test_collect_hardware_summary_shape() -> None:
    summary = collect_hardware_summary()
    payload = summary.to_api_dict()
    assert set(payload) == {"status", "gpu", "driver", "cuda", "memory", "temperature"}
    assert payload["memory"]
