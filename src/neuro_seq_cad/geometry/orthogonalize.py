from __future__ import annotations

import math

from neuro_seq_cad.geometry.primitives import Point2D, Segment2D


SNAP_ANGLES = (0.0, 45.0, 90.0, 135.0, 180.0, -45.0, -90.0, -135.0)


def nearest_snap_angle(angle: float, tolerance: float = 7.5) -> float | None:
    """가까운 표준 도면 각도를 찾는다.

    평면도 선은 대부분 수평/수직이고 일부 사선은 45도 계열이다.
    다만 실제 스캔에는 비뚤어짐이 있으므로 허용 오차 안에 들어올 때만
    보정한다.
    """

    normalized = ((angle + 180) % 360) - 180
    best = min(SNAP_ANGLES, key=lambda a: abs(normalized - a))
    return best if abs(normalized - best) <= tolerance else None


def orthogonalize_segment(segment: Segment2D, tolerance: float = 7.5, non_manhattan_flag: bool = False) -> Segment2D:
    """Snap a segment to 0/90/45/135 degrees when it is close enough."""

    effective_tolerance = tolerance * (0.5 if non_manhattan_flag else 1.0)
    snap_angle = nearest_snap_angle(segment.angle, effective_tolerance)
    if snap_angle is None:
        return segment
    length = segment.length
    radians = math.radians(snap_angle)
    p2 = Point2D(segment.p1.x + math.cos(radians) * length, segment.p1.y + math.sin(radians) * length)
    return Segment2D(segment.p1, p2)

