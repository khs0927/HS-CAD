"""
polygonize — 선분 → 폴리라인/폴리곤 변환

검출된 선분들을 연결하여 닫힌 폴리곤이나 열린 폴리라인을 구성한다.
networkx 그래프를 사용하여 연결 관계를 파악하고 사이클/체인을 탐색한다.
"""

from __future__ import annotations

import logging
from typing import Sequence

from neuro_seq_cad.geometry.primitives import Line2D, Point2D

logger = logging.getLogger(__name__)

try:
    import networkx as nx

    _HAS_NX = True
except ImportError:
    _HAS_NX = False
    logger.warning(
        "networkx를 찾을 수 없습니다. polygonize 기능이 제한됩니다. "
        "'pip install networkx' 로 설치하세요."
    )


def _point_key(pt: Point2D, precision: int = 3) -> tuple[float, float]:
    """점을 그래프 노드 키로 변환한다 (좌표 반올림)."""
    return (round(pt.x, precision), round(pt.y, precision))


def _build_graph(
    lines: Sequence[Line2D],
    precision: int = 3,
) -> nx.Graph:  # type: ignore[name-defined]
    """선분 리스트로부터 networkx 그래프를 생성한다.

    각 끝점이 노드, 각 선분이 엣지.
    """
    if not _HAS_NX:
        raise RuntimeError("networkx is required for polygonize operations")

    G = nx.Graph()
    for idx, line in enumerate(lines):
        k1 = _point_key(line.p1, precision)
        k2 = _point_key(line.p2, precision)
        if k1 == k2:
            continue  # 퇴화 선분 무시
        G.add_node(k1, point=line.p1)
        G.add_node(k2, point=line.p2)
        G.add_edge(k1, k2, line_idx=idx, weight=line.length())
    return G


def lines_to_polylines(
    lines: Sequence[Line2D],
    connect_threshold: float = 10.0,
    precision: int = 3,
) -> list[list[tuple[float, float]]]:
    """선분들을 연결하여 폴리라인 시퀀스를 생성한다.

    1. 선분 끝점으로 그래프 구축
    2. 연결 컴포넌트별로 사이클(닫힌 폴리곤) 또는 체인(열린 폴리라인) 탐색
    3. 점 좌표 시퀀스 반환 (LWPOLYLINE 입력용)

    Args:
        lines: 입력 선분 리스트.
        connect_threshold: 끝점 연결 거리 임계값 (이 값은 snap이 이미 적용된 후 사용).
        precision: 좌표 반올림 소수점 자릿수.

    Returns:
        각 원소가 점 좌표 리스트인 폴리라인 모음.
    """
    if not _HAS_NX:
        # fallback: 각 선분을 독립 폴리라인으로
        logger.warning("networkx 없이 폴백 모드: 각 선분을 개별 폴리라인으로 반환")
        return [
            [line.p1.as_tuple(), line.p2.as_tuple()]
            for line in lines
            if line.length() > 1e-6
        ]

    if not lines:
        return []

    G = _build_graph(lines, precision)

    result: list[list[tuple[float, float]]] = []

    # ── 사이클 탐색 (닫힌 폴리곤) ───────────────
    # minimum_cycle_basis: 최소 사이클 기반 집합
    try:
        cycles = nx.minimum_cycle_basis(G)
        for cycle_nodes in cycles:
            if len(cycle_nodes) < 3:
                continue
            # 사이클 노드를 순서대로 정렬 (그래프 경로 순서)
            ordered = _order_cycle_nodes(G, cycle_nodes)
            if ordered:
                pts = [node for node in ordered]
                pts.append(pts[0])  # 닫기
                result.append(pts)
    except Exception:
        logger.debug("사이클 탐색 실패, 체인 탐색만 수행합니다.")

    # ── 체인 탐색 (열린 폴리라인) ─────────────────
    # 사이클에 포함되지 않은 엣지 → 별도 연결 컴포넌트에서 경로 추출
    cycle_edges: set[tuple] = set()
    for polyline in result:
        for i in range(len(polyline) - 1):
            a, b = polyline[i], polyline[i + 1]
            cycle_edges.add((a, b))
            cycle_edges.add((b, a))

    # 사이클 엣지 제거한 부분 그래프
    H = G.copy()
    for u, v in list(H.edges()):
        if (u, v) in cycle_edges or (v, u) in cycle_edges:
            H.remove_edge(u, v)

    # 남은 연결 컴포넌트에서 체인 추출
    for component in nx.connected_components(H):
        subgraph = H.subgraph(component)
        if subgraph.number_of_edges() == 0:
            continue
        chain = _extract_chain(subgraph)
        if chain and len(chain) >= 2:
            result.append(chain)

    return result


def _order_cycle_nodes(
    G: nx.Graph,  # type: ignore[name-defined]
    nodes: list,
) -> list[tuple[float, float]] | None:
    """사이클 노드를 인접 순서로 정렬한다."""
    if not _HAS_NX or len(nodes) < 3:
        return None

    node_set = set(nodes)
    ordered: list = [nodes[0]]
    visited: set = {nodes[0]}

    current = nodes[0]
    for _ in range(len(nodes) - 1):
        neighbors = [
            n for n in G.neighbors(current)
            if n in node_set and n not in visited
        ]
        if not neighbors:
            break
        # 가장 가까운 이웃 선택
        next_node = neighbors[0]
        ordered.append(next_node)
        visited.add(next_node)
        current = next_node

    if len(ordered) == len(nodes):
        return ordered
    return None


def _extract_chain(
    subgraph: nx.Graph,  # type: ignore[name-defined]
) -> list[tuple[float, float]]:
    """연결 컴포넌트에서 가장 긴 단순 경로(체인)를 추출한다.

    차수(degree) 1인 노드(leaf)를 찾아 DFS로 경로 생성.
    """
    if not _HAS_NX:
        return []

    nodes = list(subgraph.nodes())
    if not nodes:
        return []

    # leaf 노드 (차수 1) 찾기
    leaves = [n for n in nodes if subgraph.degree(n) == 1]

    if leaves:
        start = leaves[0]
    else:
        start = nodes[0]

    # DFS 순회로 체인 구성
    visited: set = set()
    chain: list[tuple[float, float]] = []
    stack = [start]

    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        chain.append(node)
        for neighbor in subgraph.neighbors(node):
            if neighbor not in visited:
                stack.append(neighbor)

    return chain


def lines_to_closed_polygons(
    lines: Sequence[Line2D],
    min_area: float = 100.0,
    precision: int = 3,
) -> list[list[tuple[float, float]]]:
    """닫힌 폴리곤만 추출한다 (최소 넓이 필터 포함).

    Args:
        lines: 입력 선분.
        min_area: 최소 넓이 (픽셀²). 이보다 작은 폴리곤은 노이즈로 제거.
        precision: 좌표 반올림 자릿수.

    Returns:
        닫힌 폴리곤의 점 시퀀스 리스트.
    """
    all_polylines = lines_to_polylines(lines, precision=precision)

    closed: list[list[tuple[float, float]]] = []
    for pts in all_polylines:
        if len(pts) < 4:  # 최소 삼각형 + 닫기 점
            continue
        # 시작점 == 끝점이면 닫힌 폴리곤
        if pts[0] == pts[-1]:
            # Shoelace 넓이 계산
            area = _shoelace_area(pts)
            if area >= min_area:
                closed.append(pts)

    return closed


def _shoelace_area(pts: list[tuple[float, float]]) -> float:
    """Shoelace 공식으로 다각형 넓이를 계산한다."""
    n = len(pts)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        j = (i + 1) % n
        s += pts[i][0] * pts[j][1]
        s -= pts[j][0] * pts[i][1]
    return abs(s) / 2.0
