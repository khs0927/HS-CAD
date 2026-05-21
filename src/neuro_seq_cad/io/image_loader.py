from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LoadedImage:
    path: Path
    width: int
    height: int
    backend: str


def _png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        sig = f.read(24)
    if sig[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Unsupported image format without optional backend: {path}")
    return struct.unpack(">II", sig[16:24])


def load_image(path: str | Path) -> LoadedImage:
    image_path = Path(path)
    if not image_path.exists():
        raise FileNotFoundError(image_path)

    try:
        from PIL import Image  # type: ignore

        with Image.open(image_path) as img:
            return LoadedImage(image_path, int(img.width), int(img.height), "pillow")
    except Exception:
        width, height = _png_size(image_path)
        return LoadedImage(image_path, width, height, "png-header")

