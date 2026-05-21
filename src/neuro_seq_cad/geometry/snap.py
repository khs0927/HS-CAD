from __future__ import annotations

import math


def snap_points(points: list[tuple[float, float]], threshold: float = 5.0) -> list[tuple[float, float]]:
    snapped: list[tuple[float, float]] = []
    for point in points:
        found = None
        for existing in snapped:
            if math.hypot(point[0] - existing[0], point[1] - existing[1]) <= threshold:
                found = existing
                break
        snapped.append(found or point)
    return snapped

