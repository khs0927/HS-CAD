from __future__ import annotations

from math import fabs
from typing import Any

from src.utils.geometry import bbox_from_points


def _polygon_area(points: list[list[float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        area += float(point[0]) * float(next_point[1])
        area -= float(next_point[0]) * float(point[1])
    return fabs(area) / 2.0


def _bbox_list(points: list[list[float]]) -> list[float]:
    """Return [min_x, min_y, max_x, max_y] from project bbox helper output."""
    bbox = bbox_from_points(points)
    if not bbox:
        return []
    return [float(bbox['min_x']), float(bbox['min_y']), float(bbox['max_x']), float(bbox['max_y'])]


def _bbox_area(bbox: list[float]) -> float:
    if len(bbox) != 4:
        return 0.0
    width = max(0.0, float(bbox[2]) - float(bbox[0]))
    height = max(0.0, float(bbox[3]) - float(bbox[1]))
    return width * height


def _confidence(points: list[list[float]], bbox: list[float], area: float) -> float:
    if len(points) < 4:
        return 0.3
    bbox_area = _bbox_area(bbox)
    fill_ratio = area / bbox_area if bbox_area else 0.0
    score = 0.35
    if len(points) >= 4:
        score += 0.25
    if area > 0:
        score += 0.25
    if 0.2 <= fill_ratio <= 1.05:
        score += 0.15
    return min(1.0, round(score, 3))


def closed_polyline_candidates(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return closed polyline-like candidates with geometry evidence.

    These candidates are intentionally generic. Later architecture workers can
    decide whether a candidate is a room boundary, wall loop, slab edge, panel
    outline, or non-architectural closed shape.
    """
    out: list[dict[str, Any]] = []
    for item in objects:
        points = item.get('points') or []
        if item.get('closed') is True and points:
            bbox = _bbox_list(points)
            area = _polygon_area(points)
            row = dict(item)
            row['bbox'] = bbox
            row['area'] = area
            row['bbox_area'] = _bbox_area(bbox)
            row['candidate_type'] = 'closed_polyline_boundary'
            row['confidence'] = _confidence(points, bbox, area)
            out.append(row)
    return out


def boundary_summary(objects: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = closed_polyline_candidates(objects)
    total_area = sum(float(item.get('area') or 0) for item in candidates)
    return {
        'candidate_count': len(candidates),
        'total_candidate_area': total_area,
        'candidates': candidates,
    }
