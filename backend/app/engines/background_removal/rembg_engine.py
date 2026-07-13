"""rembg-backed background removal engine."""

from pathlib import Path

from rembg import remove

from app.engines.background_removal.base import BackgroundRemovalEngine


class RemBGBackgroundRemovalEngine(BackgroundRemovalEngine):
    """Remove image backgrounds using the rembg library."""

    name = "rembg"

    def remove_background(self, source: Path, destination: Path) -> None:
        input_bytes = source.read_bytes()
        output_bytes = remove(input_bytes)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(output_bytes)
