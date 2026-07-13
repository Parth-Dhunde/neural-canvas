"""Background removal engine abstraction."""

from abc import ABC, abstractmethod
from pathlib import Path


class BackgroundRemovalEngine(ABC):
    """Interface for per-image background removal engines."""

    name: str

    @abstractmethod
    def remove_background(self, source: Path, destination: Path) -> None:
        """Remove the background from ``source`` and write to ``destination``."""
