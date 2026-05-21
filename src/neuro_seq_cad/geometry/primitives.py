from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float


@dataclass(frozen=True)
class Segment2D:
    p1: Point2D
    p2: Point2D

    @property
    def length(self) -> float:
        return math.hypot(self.p2.x - self.p1.x, self.p2.y - self.p1.y)

    @property
    def angle(self) -> float:
        return math.degrees(math.atan2(self.p2.y - self.p1.y, self.p2.x - self.p1.x))


@dataclass(frozen=True)
class Polygon2D:
    points: list[Point2D]


def bbox_from_points(points: Iterable[Point2D]) -> tuple[float, float, float, float]:
    pts = list(points)
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    return min(xs), min(ys), max(xs), max(ys)

