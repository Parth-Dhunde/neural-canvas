"""Tests for text helpers."""

from __future__ import annotations

from app.core.text import strip_ansi


def test_strip_ansi_removes_color_codes() -> None:
    raw = "\x1b[0;31mE20260919 failed\x1b[m"
    assert strip_ansi(raw) == "E20260919 failed"
