"""
merge_lines — 공선(collinear) 선분 병합

같은 방향이고 같은 축에 가까운 선분을 하나의 긴 선분으로 합친다.
벽체 선분이 여러 개로 분절되어 검출될 때 사용한다.
"""

from __future__ import annotations

import math
from typing import Sequence

from neuro_seq_cad.geometry.primitives import Line2D, Point2D


def _angle_diff(a_deg: float, b_deg: float) -> float:
    """두 각도 사이의 최소 차이 (0~90)를 반환한다.

    선분 방향은 180도 주기이므로 0~90 범위로 정규화한다.
    """
    diff = abs((a_deg % 180.0) - (b_deg % 180.0))
    if diff > 90.0:
        diff = 180.0 - diff
    return diff


def _perpendicular_distance(line: Line2D, pt: Point2D) -> float:
    """한 선분 위 점에서 다른 선분까지의 수직 거리가 임계값 이하인지 확인하기 위한 수직 거리 계산.

    수직 거리 = |외적| / |선분 길이|
    """
    return line.point_distance(pt)


def _gap_distance(line_a: Line2D, line_b: Line2D) -> float:
    """두 선분 끝점 간 축 방향 간격을 반환한다.

    두 선분의 투영 범위가 겹치면 0, 아니면 간격.
    """
    # A의 방향 벡터를 기준으로 B의 끝점을 투영
    dx, dy = line_a.direction()
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return float("inf")

    # 기준점 = A의 p1
    def project(pt: Point2D) -> float:
        return (pt.x - line_a.p1.x) * dx + (pt.y - line_a.p1.y) * dy

    a_t1 = 0.0
    a_t2 = project(line_a.p2)
    b_t1 = project(line_b.p1)
    b_t2 = project(line_b.p2)

    a_min, a_max = min(a_t1, a_t2), max(a_t1, a_t2)
    b_min, b_max = min(b_t1, b_t2), max(b_t1, b_t2)

    if a_max < b_min:
        return b_min - a_max
    if b_max < a_min:
        return a_min - b_max
    return 0.0  # 겹침


def _merge_two_lines(line_a: Line2D, line_b: Line2D) -> Line2D:
    """두 선분의 모든 끝점 중 가장 먼 쌍을 새 선분으로 만든다.

    병합: 두 선분의 모든 끝점 중 가장 먼 쌍을 새 선분으로.
    """
    points = [line_a.p1, line_a.p2, line_b.p1, line_b.p2]
    best_dist = -1.0
    best_pair = (points[0], points[1])

    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            d = points[i].distance_to(points[j])
            if d > best_dist:
                best_dist = d
                best_pair = (points[i], points[j])

    return Line2D(p1=best_pair[0], p2=best_pair[1])


def merge_collinear_lines(
    lines: Sequence[Line2D],
    angle_thresh: float = 5.0,
    dist_thresh: float = 10.0,
    gap_thresh: float = 15.0,
) -> list[Line2D]:
    """같은 방향이고 같은 축에 가까운 선분은 하나의 긴 선분으로 병합한다.

    방향: 각도 차이가 임계값 이하.
    축 근접: 한 선분 위 점에서 다른 선분까지의 수직 거리가 임계값 이하.
    병합: 두 선분의 모든 끝점 중 가장 먼 쌍을 새 선분으로.

    Args:
        lines: 입력 선분 리스트.
        angle_thresh: 방향 차이 임계값 (도).
        dist_thresh: 수직 거리 임계값 (픽셀).
        gap_thresh: 축 방향 간격 임계값 (픽셀).

    Returns:
        병합된 Line2D 리스트.
    """
    if not lines:
        return []

    # 작업 리스트 (mutable)
    work: list[Line2D | None] = list(lines)
    merged = True

    while merged:
        merged = False
        n = len(work)

        for i in range(n):
            if work[i] is None:
                continue
            for j in range(i + 1, n):
                if work[j] is None:
                    continue

                line_a = work[i]
                line_b = work[j]
                assert line_a is not None and line_b is not None

                # 방향: 각도 차이가 임계값 이하
                angle_a = line_a.angle_deg()
                angle_b = line_b.angle_deg()
                if _angle_diff(angle_a, angle_b) > angle_thresh:
                    continue

                # 축 근접: 한 선분 위 점에서 다른 선분까지의 수직 거리가 임계값 이하
                perp_b1 = _perpendicular_distance(line_a, line_b.p1)
                perp_b2 = _perpendicular_distance(line_a, line_b.p2)
                if min(perp_b1, perp_b2) > dist_thresh:
                    continue

                # 간격(gap) 검사
                gap = _gap_distance(line_a, line_b)
                if gap > gap_thresh:
                    continue

                # 병합: 두 선분의 모든 끝점 중 가장 먼 쌍을 새 선분으로
                merged_line = _merge_two_lines(line_a, line_b)
                work[i] = merged_line
                work[j] = None
                merged = True

        # None 제거
        work = [ln for ln in work if ln is not None]

    return [ln for ln in work if ln is not None]


def merge_collinear_lines_fast(
    lines: Sequence[Line2D],
    angle_thresh: float = 5.0,
    dist_thresh: float = 10.0,
    gap_thresh: float = 15.0,
    max_iterations: int = 10,
) -> list[Line2D]:
    """반복 횟수 상한이 있는 병합 (무한 루프 방지).

    대규모 선분 세트에서 수렴이 느릴 경우를 대비한다.
    """
    result = list(lines)
    for _ in range(max_iterations):
        prev_count = len(result)
        result = merge_collinear_lines(result, angle_thresh, dist_thresh, gap_thresh)
        if len(result) == prev_count:
            break  # 더 이상 병합 없음
    return result
