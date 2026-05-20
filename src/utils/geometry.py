from __future__ import annotations
from typing import Iterable

Point = list[float]

def chunk_points(coords: Iterable[float], size: int = 2) -> list[list[float]]:
    vals = list(coords or [])
    return [vals[i:i+size] for i in range(0, len(vals), size) if len(vals[i:i+size]) == size]

def bbox_from_points(points: list[list[float]]) -> dict[str, float] | None:
    if not points:
        return None
    xs = [p[0] for p in points if len(p) >= 2]
    ys = [p[1] for p in points if len(p) >= 2]
    if not xs or not ys:
        return None
    return {"min_x": min(xs), "min_y": min(ys), "max_x": max(xs), "max_y": max(ys), "width": max(xs)-min(xs), "height": max(ys)-min(ys)}
