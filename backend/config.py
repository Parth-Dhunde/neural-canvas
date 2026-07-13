"""Configuration re-export for convenience.

Settings are defined in ``app.core.config``.
"""

from app.core.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
