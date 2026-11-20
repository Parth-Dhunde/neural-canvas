"""Structured logging configuration."""

import logging
import sys

from app.core.config import get_settings


def setup_logging() -> None:
    """Configure root logger with a structured console handler."""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
        force=True,
    )

    if settings.debug:
        logging.getLogger("uvicorn.access").setLevel(logging.DEBUG)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
