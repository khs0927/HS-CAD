from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import win32com.client
from PIL import Image, ImageDraw, ImageFont

DOCUMENT_NAME = "Drawing1.dwg"
OUTPUT = Path(__file__).resolve().parents[1] / "outputs" / "clean-mcp-demo-preview.png"
WIDTH = 1400
HEIGHT = 820
PADDING = 70

LAYER_COLORS = {
    "HSCAD_MCP_WALL": "#e6e9ee",
    "HSCAD_MCP_DOOR": "#35e05b",
    "HSCAD_MCP_TEXT": "#f2f5f8",
    "HSCAD_MCP_ANNO": "#ffcc33",
}


def _point(value: Any) -> tuple[float, float, float]:
    values = tuple(float(item) for item in value)
    return values[0], values[1], values[2] if len(values) > 2 else 0.0


def _bbox(entity: Any) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    minimum, maximum = entity.GetBoundingBox()
    return _point(minimum), _point(maximum)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("arial.ttf", "malgun.ttf"):
        try:
            return ImageFont.truetype(name, max(14, size))
        except OSError:
            continue
    return ImageFont.load_default()


def render() -> dict[str, Any]:
    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    documents = [doc for doc in app.Documents if str(doc.Name).casefold() == DOCUMENT_NAME.casefold()]
    if len(documents) != 1:
        raise RuntimeError(f"expected one {DOCUMENT_NAME}, found {len(documents)}")
    entities = list(documents[0].ModelSpace)
    if not entities:
        raise RuntimeError("Drawing1.dwg is empty")

    boxes = [_bbox(entity) for entity in entities]
    min_x = min(box[0][0] for box in boxes)
    min_y = min(box[0][1] for box in boxes)
    max_x = max(box[1][0] for box in boxes)
    max_y = max(box[1][1] for box in boxes)
    scale = min((WIDTH - 2 * PADDING) / (max_x - min_x), (HEIGHT - 2 * PADDING) / (max_y - min_y))

    def screen(point: Any) -> tuple[float, float]:
        x, y, _z = _point(point)
        return PADDING + (x - min_x) * scale, HEIGHT - PADDING - (y - min_y) * scale

    image = Image.new("RGB", (WIDTH, HEIGHT), "#17212b")
    draw = ImageDraw.Draw(image)
    grid = 50
    for x in range(0, WIDTH, grid):
        draw.line((x, 0, x, HEIGHT), fill="#202d38", width=1)
    for y in range(0, HEIGHT, grid):
        draw.line((0, y, WIDTH, y), fill="#202d38", width=1)

    counts: dict[str, int] = {}
    for entity in entities:
        name = str(entity.ObjectName)
        counts[name] = counts.get(name, 0) + 1
        color = LAYER_COLORS.get(str(entity.Layer), "#c8d0d8")
        folded = name.casefold()
        if folded == "acdbline":
            draw.line((*screen(entity.StartPoint), *screen(entity.EndPoint)), fill=color, width=3)
        elif folded == "acdbarc":
            center = _point(entity.Center)
            radius = float(entity.Radius)
            start = float(entity.StartAngle)
            end = float(entity.EndAngle)
            if end < start:
                end += math.tau
            points = [
                screen((center[0] + radius * math.cos(start + (end - start) * i / 40), center[1] + radius * math.sin(start + (end - start) * i / 40), 0))
                for i in range(41)
            ]
            draw.line(points, fill=color, width=3)
        elif folded in {"acdbleader", "acdb2dleader"}:
            coords = tuple(float(value) for value in entity.Coordinates)
            points = [screen(coords[index : index + 3]) for index in range(0, len(coords), 3)]
            draw.line(points, fill=color, width=3)
            if len(points) >= 2:
                tip, next_point = points[0], points[1]
                angle = math.atan2(tip[1] - next_point[1], tip[0] - next_point[0])
                arrow = [
                    tip,
                    (tip[0] - 14 * math.cos(angle - 0.45), tip[1] - 14 * math.sin(angle - 0.45)),
                    (tip[0] - 14 * math.cos(angle + 0.45), tip[1] - 14 * math.sin(angle + 0.45)),
                ]
                draw.polygon(arrow, fill=color)
        elif folded == "acdbmtext":
            insertion = screen(entity.InsertionPoint)
            font_size = int(float(entity.Height) * scale)
            draw.text(insertion, str(entity.TextString), fill=color, font=_font(font_size), anchor="ls")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT)
    return {
        "document": DOCUMENT_NAME,
        "output": str(OUTPUT),
        "object_count": len(entities),
        "type_counts": counts,
        "world_bbox": {"min": [min_x, min_y], "max": [max_x, max_y]},
        "pixels_per_drawing_unit": scale,
    }


if __name__ == "__main__":
    print(json.dumps(render(), ensure_ascii=False, indent=2))
