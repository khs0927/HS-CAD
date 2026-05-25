from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float


@dataclass(frozen=True)
class BBox2D:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def contains(self, point: Point2D) -> bool:
        return self.min_x <= point.x <= self.max_x and self.min_y <= point.y <= self.max_y

    def intersects(self, other: 'BBox2D') -> bool:
        if self.max_x < other.min_x:
            return False
        if self.min_x > other.max_x:
            return False
        if self.max_y < other.min_y:
            return False
        if self.min_y > other.max_y:
            return False
        return True


def as_point2d(value: object) -> Point2D | None:
    if value is None:
        return None
    try:
        seq = list(value)  # type: ignore[arg-type]
        return Point2D(float(seq[0]), float(seq[1]))
    except Exception:
        return None


def bbox_from_points(points: Iterable[Point2D]) -> BBox2D | None:
    pts = list(points)
    if not pts:
        return None
    return BBox2D(
        min_x=min(p.x for p in pts),
        min_y=min(p.y for p in pts),
        max_x=max(p.x for p in pts),
        max_y=max(p.y for p in pts),
    )
