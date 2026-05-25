from __future__ import annotations

import math
from typing import Any

from src.spatial.geometry import BBox2D, Point2D, as_point2d, bbox_from_points


def iter_texts(entities: list[dict[str, Any]]) -> list[tuple[dict[str, Any], Point2D]]:
    rows: list[tuple[dict[str, Any], Point2D]] = []
    for entity in entities:
        entity_type = str(entity.get('entity_type') or '').upper()
        if entity_type not in {'TEXT', 'MTEXT'}:
            continue
        point = as_point2d(entity.get('insert'))
        if point is not None:
            rows.append((entity, point))
    return rows


def iter_lines(entities: list[dict[str, Any]]) -> list[tuple[dict[str, Any], Point2D, Point2D]]:
    rows: list[tuple[dict[str, Any], Point2D, Point2D]] = []
    for entity in entities:
        if str(entity.get('entity_type') or '').upper() != 'LINE':
            continue
        start = as_point2d(entity.get('start'))
        end = as_point2d(entity.get('end'))
        if start is not None and end is not None:
            rows.append((entity, start, end))
    return rows


def distance_point_to_segment(point: Point2D, start: Point2D, end: Point2D) -> float:
    dx = end.x - start.x
    dy = end.y - start.y
    if dx == 0 and dy == 0:
        return math.hypot(point.x - start.x, point.y - start.y)
    t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    px = start.x + t * dx
    py = start.y + t * dy
    return math.hypot(point.x - px, point.y - py)


def drawing_bbox(entities: list[dict[str, Any]]) -> BBox2D | None:
    points: list[Point2D] = []
    for entity in entities:
        for key in ('insert', 'start', 'end', 'center'):
            point = as_point2d(entity.get(key))
            if point is not None:
                points.append(point)
        for raw in entity.get('points') or []:
            point = as_point2d(raw)
            if point is not None:
                points.append(point)
    return bbox_from_points(points)


def text_content(entity: dict[str, Any]) -> str:
    return str(entity.get('text') or '').strip()
