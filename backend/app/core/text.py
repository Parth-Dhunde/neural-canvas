"""Small text helpers."""

from __future__ import annotations

import re

# SGR colors plus cursor/erase sequences such as ``\x1b[K`` emitted by Instant-NGP.
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

# COLMAP uses glog prefixes (``E20261015 ...``); Instant-NGP prints ``ERROR``/``WARNING`` tags.
_ERROR_LINE = re.compile(
    r"^[EF]\d{8}\s|\b(ERROR|FATAL)\b|^Traceback \(most recent call last\)|^\w*(Error|Exception):"
)
_WARN_LINE = re.compile(r"^W\d{8}\s|\bWARN(ING)?\b")
_SUCCESS_LINE = re.compile(r"\bSUCCESS\b")


def strip_ansi(text: str) -> str:
    """Remove terminal color/control sequences from ``text``."""
    return _ANSI_ESCAPE.sub("", text).strip()


def infer_log_level(line: str) -> str:
    """Return ``error``, ``warn``, ``ok`` or ``info`` from explicit severity markers in ``line``."""
    # Strip colors first: in "\x1b[0;33mWARNING" the escape's trailing "m" defeats \b matching.
    line = strip_ansi(line)
    if _ERROR_LINE.search(line):
        return "error"
    if _WARN_LINE.search(line):
        return "warn"
    if _SUCCESS_LINE.search(line):
        return "ok"
    return "info"
