"""
orthogonalize — 선분의 직교화 처리

건축 도면에서 대부분의 벽체 선분은 수평/수직 또는 45도 방향이다.
이 모듈은 미세하게 기울어진 선분을 가장 가까운 표준 각도로 스냅한다.
"""

from __future__ import annotations

import math
from typing import Sequence

from neuro_seq_cad.geometry.primitives import Line2D, Point2D

# ── 스냅 대상 각도 (도 단위) ─────────────────
# 0°(→), 45°(↗), 90°(↑), 135°(↖), 180°(←), 225°(↙), 270°(↓), 315°(↘)
_SNAP_ANGLES_DEG: list[float] = [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0, 360.0]


def _normalize_angle_deg(angle_deg: float) -> float:
    """각도를 [0, 360) 범위로 정규화한다."""
    return angle_deg % 360.0


def _find_nearest_snap_angle(angle_deg: float, threshold_deg: float) -> float | None:
    """가장 가까운 스냅 각도를 찾는다.

    Args:
        angle_deg: 선분의 각도 (0 ~ 360).
        threshold_deg: 스냅 임계값 (기본 7.5도).

    Returns:
        스냅 각도 (도), 없으면 None.
    """
    # 선분의 각도를 계산한다
    norm = _normalize_angle_deg(angle_deg)
    best_snap: float | None = None
    best_diff = float("inf")

    for snap in _SNAP_ANGLES_DEG:
        # 0도, 90도에 가까우면 해당 각도로 스냅한다
        diff = abs(norm - snap)
        # 360도 경계 처리
        if diff > 180.0:
            diff = 360.0 - diff
        if diff < best_diff:
            best_diff = diff
            best_snap = snap

    # 스냅 임계값은 기본 7.5도
    if best_diff <= threshold_deg and best_snap is not None:
        # 360도는 0도와 동일
        return best_snap % 360.0
    return None


def orthogonalize_line(
    p1: Point2D,
    p2: Point2D,
    threshold_deg: float = 7.5,
) -> tuple[Point2D, Point2D]:
    """선분 하나를 직교화한다.

    선분의 각도를 계산한다.
    0도, 90도에 가까우면 해당 각도로 스냅한다.
    스냅 임계값은 기본 7.5도.
    길이는 유지하고 중심점 기준으로 회전한다.

    Args:
        p1: 시작점.
        p2: 끝점.
        threshold_deg: 각도 스냅 임계값 (도).

    Returns:
        (new_p1, new_p2): 직교화된 선분 끝점 쌍.
    """
    # 선분의 각도를 계산한다
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    current_angle_rad = math.atan2(dy, dx)
    current_angle_deg = _normalize_angle_deg(math.degrees(current_angle_rad))

    # 0도, 90도에 가까우면 해당 각도로 스냅한다
    snap_angle_deg = _find_nearest_snap_angle(current_angle_deg, threshold_deg)

    if snap_angle_deg is None:
        # 스냅 대상이 아니면 원래 선분 유지
        return (p1, p2)

    # 스냅 각도와 현재 각도의 차이 (회전량)
    rotation_deg = snap_angle_deg - current_angle_deg
    # 최단 회전 경로 선택 (-180 ~ +180)
    if rotation_deg > 180.0:
        rotation_deg -= 360.0
    elif rotation_deg < -180.0:
        rotation_deg += 360.0
    rotation_rad = math.radians(rotation_deg)

    # 길이는 유지하고 중심점 기준으로 회전한다
    mid = p1.midpoint_to(p2)
    new_p1 = p1.rotate_around(mid, rotation_rad)
    new_p2 = p2.rotate_around(mid, rotation_rad)

    return (new_p1, new_p2)


def orthogonalize_lines(
    lines: Sequence[Line2D],
    threshold_deg: float = 7.5,
) -> list[Line2D]:
    """여러 선분에 대해 직교화를 일괄 적용한다.

    Args:
        lines: 입력 선분 리스트.
        threshold_deg: 각도 스냅 임계값 (도).

    Returns:
        직교화된 Line2D 리스트.
    """
    result: list[Line2D] = []
    for line in lines:
        new_p1, new_p2 = orthogonalize_line(line.p1, line.p2, threshold_deg)
        result.append(Line2D(p1=new_p1, p2=new_p2))
    return result


def orthogonalize_to_dominant(
    lines: Sequence[Line2D],
    threshold_deg: float = 7.5,
    bin_size_deg: float = 5.0,
) -> list[Line2D]:
    """지배적인 방향(dominant orientation)에 맞춰 직교화한다.

    건물 전체가 약간 기울어진 경우, 먼저 지배적 방향을 찾고
    그 방향과 수직 방향에 맞춰 스냅한다.

    1단계: 길이 가중 히스토그램으로 지배적 각도 빈 탐색
    2단계: 각 선분을 지배적 각도 또는 그 수직 방향으로 스냅

    Args:
        lines: 입력 선분.
        threshold_deg: 스냅 임계값.
        bin_size_deg: 히스토그램 빈 크기.

    Returns:
        직교화된 Line2D 리스트.
    """
    if not lines:
        return []

    # ── 1단계: 길이 가중 히스토그램 생성 ──────
    n_bins = int(180.0 / bin_size_deg)
    histogram = [0.0] * n_bins

    for line in lines:
        angle = line.angle_deg() % 180.0  # 방향 무시, 0~180
        bin_idx = int(angle / bin_size_deg) % n_bins
        histogram[bin_idx] += line.length()

    # 최대 빈 → 지배적 방향
    dominant_bin = max(range(n_bins), key=lambda i: histogram[i])
    dominant_angle = (dominant_bin + 0.5) * bin_size_deg  # 빈 중앙

    # ── 2단계: 지배적 각도 + 90도 방향으로 스냅 ──
    snap_targets = [
        _normalize_angle_deg(dominant_angle),
        _normalize_angle_deg(dominant_angle + 90.0),
        _normalize_angle_deg(dominant_angle + 180.0),
        _normalize_angle_deg(dominant_angle + 270.0),
    ]

    result: list[Line2D] = []
    for line in lines:
        current_deg = line.angle_deg()
        best_snap = None
        best_diff = float("inf")

        for snap in snap_targets:
            diff = abs(current_deg - snap)
            if diff > 180.0:
                diff = 360.0 - diff
            if diff < best_diff:
                best_diff = diff
                best_snap = snap

        if best_diff <= threshold_deg and best_snap is not None:
            rotation_deg = best_snap - current_deg
            if rotation_deg > 180.0:
                rotation_deg -= 360.0
            elif rotation_deg < -180.0:
                rotation_deg += 360.0
            rotation_rad = math.radians(rotation_deg)
            mid = line.midpoint()
            new_p1 = line.p1.rotate_around(mid, rotation_rad)
            new_p2 = line.p2.rotate_around(mid, rotation_rad)
            result.append(Line2D(p1=new_p1, p2=new_p2))
        else:
            result.append(line)

    return result
