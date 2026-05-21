from __future__ import annotations

import math


def offset_centerline_to_wall_polygon(p1: tuple[float, float], p2: tuple[float, float], thickness: float) -> tuple[list[tuple[float, float]], list[str]]:
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return [], ["open_wall_polygon: zero-length centerline"]
    nx = -dy / length * thickness / 2.0
    ny = dx / length * thickness / 2.0
    return [
        (p1[0] + nx, p1[1] + ny),
        (p2[0] + nx, p2[1] + ny),
        (p2[0] - nx, p2[1] - ny),
        (p1[0] - nx, p1[1] - ny),
    ], []

