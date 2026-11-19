"""Per-job pipeline log storage with incremental (cursor-based) retrieval.

Each job keeps a bounded in-memory ring buffer of recent entries for polling and appends
every entry to ``jobs/<job_id>/logs/pipeline.jsonl`` so history survives restarts and
clearing the dashboard terminal. Sequence numbers are per job and strictly increasing.
"""

from __future__ import annotations

import json
import threading
from collections import OrderedDict, deque
from dataclasses import asdict, dataclass
from pathlib import Path

from app.core.logging import get_logger
from app.core.text import strip_ansi
from app.jobs.structure import pipeline_log_path
from app.models.job import utc_now_iso

logger = get_logger(__name__)

DEFAULT_MAX_ENTRIES = 3000
DEFAULT_MAX_JOBS = 16
DEFAULT_MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_PAGE_SIZE = 1000

_LEVEL_ALIASES = {"warning": "warn", "success": "ok", "critical": "error", "exception": "error"}
_LEVELS = frozenset({"debug", "info", "ok", "warn", "error"})


@dataclass(frozen=True)
class LogEntry:
    """A single pipeline log line."""

    seq: int
    time: str
    level: str
    message: str
    stage_id: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class LogPage:
    """Result of an incremental log read."""

    entries: list[LogEntry]
    last_seq: int
    first_seq: int
    next_after: int
    has_more: bool
    truncated: bool
    reset: bool


class _JobBuffer:
    def __init__(self, max_entries: int) -> None:
        self.entries: deque[LogEntry] = deque(maxlen=max_entries)
        self.last_seq = 0


def normalize_level(level: str) -> str:
    """Map logger-style level names onto the API's level vocabulary."""
    value = _LEVEL_ALIASES.get(level.lower(), level.lower())
    return value if value in _LEVELS else "info"


class JobLogStore:
    """Thread-safe store; stage subprocess readers append from worker threads."""

    def __init__(
        self,
        jobs_root: Path,
        *,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        max_jobs: int = DEFAULT_MAX_JOBS,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    ) -> None:
        self._jobs_root = jobs_root
        self._max_entries = max_entries
        self._max_jobs = max_jobs
        self._max_file_bytes = max_file_bytes
        self._buffers: OrderedDict[str, _JobBuffer] = OrderedDict()
        self._lock = threading.Lock()

    def append(
        self,
        job_id: str,
        message: str,
        *,
        level: str = "info",
        stage_id: int | None = None,
    ) -> LogEntry:
        """Record ``message`` for ``job_id`` and persist it."""
        with self._lock:
            buffer = self._buffer(job_id)
            buffer.last_seq += 1
            entry = LogEntry(
                seq=buffer.last_seq,
                time=utc_now_iso(),
                level=normalize_level(level),
                message=strip_ansi(message),
                stage_id=stage_id,
            )
            buffer.entries.append(entry)
            self._persist(job_id, entry)
            return entry

    def read(
        self,
        job_id: str,
        *,
        after: int = 0,
        limit: int = 500,
        tail: int | None = None,
    ) -> LogPage:
        """Return entries with ``seq > after`` (or the last ``tail`` entries)."""
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        with self._lock:
            buffer = self._buffer(job_id)
            entries = list(buffer.entries)
            last_seq = buffer.last_seq

        first_seq = entries[0].seq if entries else last_seq + 1
        reset = after > last_seq
        if reset:
            after = 0

        if tail is not None:
            selected = entries[-max(1, min(tail, MAX_PAGE_SIZE)) :] if entries else []
            truncated = bool(selected) and selected[0].seq > first_seq
            has_more = False
            next_after = selected[-1].seq if selected else last_seq
        else:
            pending = [entry for entry in entries if entry.seq > after]
            selected = pending[:limit]
            has_more = len(pending) > limit
            # Entries between the cursor and the oldest buffered one were evicted from memory.
            truncated = bool(entries) and after + 1 < first_seq
            next_after = selected[-1].seq if selected else after

        return LogPage(
            entries=selected,
            last_seq=last_seq,
            first_seq=first_seq,
            next_after=next_after,
            has_more=has_more,
            truncated=truncated,
            reset=reset,
        )

    def last_seq(self, job_id: str) -> int:
        with self._lock:
            return self._buffer(job_id).last_seq

    def _buffer(self, job_id: str) -> _JobBuffer:
        buffer = self._buffers.get(job_id)
        if buffer is not None:
            self._buffers.move_to_end(job_id)
            return buffer

        buffer = _JobBuffer(self._max_entries)
        self._restore(job_id, buffer)
        self._buffers[job_id] = buffer
        while len(self._buffers) > self._max_jobs:
            self._buffers.popitem(last=False)
        return buffer

    def _restore(self, job_id: str, buffer: _JobBuffer) -> None:
        """Load the tail of the persisted log so cursors stay valid across restarts."""
        path = pipeline_log_path(self._jobs_root, job_id)
        if not path.is_file():
            return
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                lines = deque(handle, maxlen=self._max_entries)
        except OSError:
            logger.warning("Could not read pipeline log | job_id=%s path=%s", job_id, path)
            return

        for line in lines:
            try:
                data = json.loads(line)
                entry = LogEntry(
                    seq=int(data["seq"]),
                    time=str(data["time"]),
                    level=normalize_level(str(data.get("level", "info"))),
                    message=str(data.get("message", "")),
                    stage_id=data.get("stage_id"),
                )
            except (ValueError, KeyError, TypeError):
                continue
            if entry.seq <= buffer.last_seq:
                continue
            buffer.entries.append(entry)
            buffer.last_seq = entry.seq

    def _persist(self, job_id: str, entry: LogEntry) -> None:
        path = pipeline_log_path(self._jobs_root, job_id)
        try:
            if not path.parent.parent.is_dir():
                return  # Unknown job workspace: keep the entry in memory only.
            path.parent.mkdir(exist_ok=True)
            if path.is_file() and path.stat().st_size >= self._max_file_bytes:
                path.replace(path.with_name(path.name + ".1"))
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry.to_dict()) + "\n")
        except OSError:
            logger.warning("Could not persist pipeline log | job_id=%s path=%s", job_id, path)


_stores: dict[Path, JobLogStore] = {}
_stores_lock = threading.Lock()


def get_job_log_store(jobs_root: Path) -> JobLogStore:
    """Return the process-wide log store for ``jobs_root``."""
    key = jobs_root.resolve()
    with _stores_lock:
        store = _stores.get(key)
        if store is None:
            store = JobLogStore(key)
            _stores[key] = store
        return store
