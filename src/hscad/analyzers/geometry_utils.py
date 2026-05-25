"""Small geometry utilities without external dependencies."""
from __future__ import annotations

import math
from typing import Iterable

Point = tuple[float, float]


def distance(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def polyline_length(points: Iterable[Point], closed: bool = False) -> float:
    pts = list(points)
    if len(pts) < 2:
        return 0.0
    total = sum(distance(a, b) for a, b in zip(pts, pts[1:]))
    if closed:
        total += distance(pts[-1], pts[0])
    return total


def polygon_area(points: Iterable[Point]) -> float:
    pts = list(points)
    if len(pts) < 3:
        return 0.0
    area = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def centroid(points: Iterable[Point]) -> Point:
    pts = list(points)
    if not pts:
        return (0.0, 0.0)
    return (sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts))
