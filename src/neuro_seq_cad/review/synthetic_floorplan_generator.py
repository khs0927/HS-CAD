from __future__ import annotations

import struct
import zlib
from pathlib import Path


def _blank_rgb(width: int, height: int, color: tuple[int, int, int]) -> bytearray:
    r, g, b = color
    return bytearray([r, g, b] * width * height)


def _set_pixel(img: bytearray, width: int, height: int, x: int, y: int, color: tuple[int, int, int]) -> None:
    if 0 <= x < width and 0 <= y < height:
        idx = (y * width + x) * 3
        img[idx:idx + 3] = bytes(color)


def _line(img: bytearray, width: int, height: int, p1: tuple[int, int], p2: tuple[int, int], color: tuple[int, int, int], thick: int = 3) -> None:
    x1, y1 = p1
    x2, y2 = p2
    dx = abs(x2 - x1)
    dy = -abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    err = dx + dy
    x, y = x1, y1
    while True:
        for ox in range(-(thick // 2), thick // 2 + 1):
            for oy in range(-(thick // 2), thick // 2 + 1):
                _set_pixel(img, width, height, x + ox, y + oy, color)
        if x == x2 and y == y2:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def _rect(img: bytearray, width: int, height: int, box: tuple[int, int, int, int], color: tuple[int, int, int], thick: int = 4) -> None:
    x1, y1, x2, y2 = box
    _line(img, width, height, (x1, y1), (x2, y1), color, thick)
    _line(img, width, height, (x2, y1), (x2, y2), color, thick)
    _line(img, width, height, (x2, y2), (x1, y2), color, thick)
    _line(img, width, height, (x1, y2), (x1, y1), color, thick)


def _arc_quarter(img: bytearray, width: int, height: int, center: tuple[int, int], radius: int, color: tuple[int, int, int]) -> None:
    cx, cy = center
    for deg in range(0, 91):
        # Deterministic door swing arc, enough for pipeline smoke tests.
        import math

        x = int(cx + math.cos(math.radians(deg)) * radius)
        y = int(cy - math.sin(math.radians(deg)) * radius)
        _set_pixel(img, width, height, x, y, color)
        _set_pixel(img, width, height, x + 1, y, color)


def _write_png(path: Path, width: int, height: int, rgb: bytearray) -> None:
    def chunk(name: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)

    scanlines = bytearray()
    row_bytes = width * 3
    for y in range(height):
        scanlines.append(0)
        start = y * row_bytes
        scanlines.extend(rgb[start:start + row_bytes])
    payload = b"\x89PNG\r\n\x1a\n"
    payload += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    payload += chunk(b"IDAT", zlib.compress(bytes(scanlines), 9))
    payload += chunk(b"IEND", b"")
    path.write_bytes(payload)


def make_synthetic_floorplan(path: str | Path, width: int = 1600, height: int = 1000) -> Path:
    """Create a deterministic floor-plan PNG without model or internet access."""

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img = _blank_rgb(width, height, (255, 255, 255))
    black = (20, 20, 20)
    blue = (30, 90, 220)
    gray = (130, 130, 130)
    green = (0, 150, 80)

    _rect(img, width, height, (180, 160, 1420, 840), black, 8)
    _line(img, width, height, (760, 160), (760, 620), black, 6)
    _line(img, width, height, (760, 710), (760, 840), black, 6)
    _line(img, width, height, (180, 510), (760, 510), black, 5)
    _line(img, width, height, (920, 160), (920, 840), black, 5)
    _line(img, width, height, (920, 510), (1420, 510), black, 5)

    # Door leaf and swing arc.
    _line(img, width, height, (760, 620), (850, 620), blue, 4)
    _arc_quarter(img, width, height, (760, 620), 90, blue)

    # Window double-line symbol.
    _line(img, width, height, (370, 160), (620, 160), green, 3)
    _line(img, width, height, (370, 178), (620, 178), green, 3)

    # Simple dimension lines.
    _line(img, width, height, (180, 910), (1420, 910), gray, 2)
    _line(img, width, height, (180, 890), (180, 930), gray, 2)
    _line(img, width, height, (1420, 890), (1420, 930), gray, 2)
    _line(img, width, height, (180, 80), (760, 80), gray, 2)
    _line(img, width, height, (180, 60), (180, 100), gray, 2)
    _line(img, width, height, (760, 60), (760, 100), gray, 2)

    _write_png(out, width, height, img)
    return out

