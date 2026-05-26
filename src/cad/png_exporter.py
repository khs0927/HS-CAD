from __future__ import annotations

from pathlib import Path


def write_png_placeholder(png_path: str | Path, message: str) -> Path:
    out = Path(png_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (1200, 800), "white")
        draw = ImageDraw.Draw(image)
        draw.text((40, 40), message, fill="black")
        image.save(out)
    except Exception:
        out.write_bytes(b"")
    return out
