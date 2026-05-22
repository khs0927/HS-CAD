"""
snap — 끝점 스냅 (endpoint snapping)

선분 검출 결과에서 가까운 끝점들을 하나의 점으로 병합한다.
Union-Find 알고리즘을 사용하여 연쇄적인 병합을 안전하게 처리한다.
"""

from __future__ import annotations

import math
from typing import Sequence

from neuro_seq_cad.geometry.primitives import Line2D, Point2D


# ──────────────────────────────────────────────
# Union-Find (Disjoint Set Union)
# 연쇄 병합 처리를 위한 자료구조
# ──────────────────────────────────────────────
class _UnionFind:
    """Union-Find 알고리즘으로 연쇄 병합 처리.

    끝점 간 거리가 임계값 이하이면 같은 점으로 병합한다.
    병합 위치는 두 점의 평균 좌표.
    Union-Find 알고리즘으로 연쇄 병합 처리.
    """

    def __init__(self, n: int) -> None:
        self._parent = list(range(n))
        self._rank = [0] * n

    def find(self, x: int) -> int:
        """경로 압축(path compression)을 적용한 find."""
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        """랭크 기반 합치기(union by rank)."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1

    def connected(self, a: int, b: int) -> bool:
        return self.find(a) == self.find(b)


def _collect_endpoints(lines: Sequence[Line2D]) -> list[Point2D]:
    """모든 선분의 끝점을 수집한다 (순서: [line0_p1, line0_p2, line1_p1, ...])."""
    pts: list[Point2D] = []
    for line in lines:
        pts.append(line.p1)
        pts.append(line.p2)
    return pts


def _compute_group_centers(
    points: list[Point2D],
    uf: _UnionFind,
) -> dict[int, Point2D]:
    """같은 그룹에 속한 점들의 평균 좌표(병합 위치)를 계산한다.

    병합 위치는 두 점의 평균 좌표.
    """
    groups: dict[int, list[Point2D]] = {}
    for idx, pt in enumerate(points):
        root = uf.find(idx)
        groups.setdefault(root, []).append(pt)

    centers: dict[int, Point2D] = {}
    for root, members in groups.items():
        cx = sum(p.x for p in members) / len(members)
        cy = sum(p.y for p in members) / len(members)
        centers[root] = Point2D(x=cx, y=cy)
    return centers


def snap_endpoints(
    lines: Sequence[Line2D],
    threshold_px: float = 5.0,
) -> list[Line2D]:
    """가까운 끝점들을 하나의 점으로 병합한다.

    끝점 간 거리가 임계값 이하이면 같은 점으로 병합한다.
    병합 위치는 두 점의 평균 좌표.
    Union-Find 알고리즘으로 연쇄 병합 처리.

    Args:
        lines: 입력 선분 리스트.
        threshold_px: 병합 거리 임계값 (픽셀).

    Returns:
        끝점이 병합된 Line2D 리스트.
    """
    if not lines:
        return []

    # 모든 끝점 수집
    endpoints = _collect_endpoints(lines)
    n = len(endpoints)

    # Union-Find 초기화
    uf = _UnionFind(n)

    # 끝점 간 거리가 임계값 이하이면 같은 점으로 병합한다
    # O(n²) — 선분 수가 수천 이하이므로 실용적
    for i in range(n):
        for j in range(i + 1, n):
            dist = endpoints[i].distance_to(endpoints[j])
            if dist <= threshold_px:
                uf.union(i, j)

    # 병합 위치는 두 점의 평균 좌표
    centers = _compute_group_centers(endpoints, uf)

    # 선분 재구성 — 각 끝점을 그룹 중심으로 교체
    result: list[Line2D] = []
    for idx, line in enumerate(lines):
        p1_idx = idx * 2
        p2_idx = idx * 2 + 1
        new_p1 = centers[uf.find(p1_idx)]
        new_p2 = centers[uf.find(p2_idx)]
        # 퇴화 선분(길이 ≈ 0) 제거
        if new_p1.distance_to(new_p2) > 1e-6:
            result.append(Line2D(p1=new_p1, p2=new_p2))

    return result


def snap_endpoints_grid(
    lines: Sequence[Line2D],
    threshold_px: float = 5.0,
) -> list[Line2D]:
    """격자(grid) 기반 공간 인덱싱으로 빠르게 끝점 스냅한다.

    선분이 수만 개 이상일 때 O(n²) 대신 O(n·k) (k ≈ 인접 셀 수).

    끝점을 격자 셀에 배치하고, 인접 셀만 검사하여 Union-Find에 등록한다.
    """
    if not lines:
        return []

    endpoints = _collect_endpoints(lines)
    n = len(endpoints)
    uf = _UnionFind(n)

    # 격자 셀 크기 = threshold (같은 셀 + 인접 셀이면 threshold 내)
    cell_size = max(threshold_px, 1e-6)

    # 점 → 셀 매핑
    grid: dict[tuple[int, int], list[int]] = {}
    for idx, pt in enumerate(endpoints):
        cx = int(math.floor(pt.x / cell_size))
        cy = int(math.floor(pt.y / cell_size))
        grid.setdefault((cx, cy), []).append(idx)

    # 각 점에 대해 인접 9개 셀만 검사
    for idx, pt in enumerate(endpoints):
        cx = int(math.floor(pt.x / cell_size))
        cy = int(math.floor(pt.y / cell_size))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                key = (cx + dx, cy + dy)
                if key not in grid:
                    continue
                for other_idx in grid[key]:
                    if other_idx <= idx:
                        continue
                    if endpoints[idx].distance_to(endpoints[other_idx]) <= threshold_px:
                        uf.union(idx, other_idx)

    centers = _compute_group_centers(endpoints, uf)

    result: list[Line2D] = []
    for idx, line in enumerate(lines):
        p1_idx = idx * 2
        p2_idx = idx * 2 + 1
        new_p1 = centers[uf.find(p1_idx)]
        new_p2 = centers[uf.find(p2_idx)]
        if new_p1.distance_to(new_p2) > 1e-6:
            result.append(Line2D(p1=new_p1, p2=new_p2))

    return result
