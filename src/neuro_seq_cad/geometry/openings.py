"""
openings.py — 벽체 라인과 문/창문 탐지 바운딩 박스를 매칭하여 개구부(Opening) 식별 및 벽체 분할

벽체(Line2D)와 문/창문 기호(SymbolDetection)의 기하학적 겹침과 거리를 분석하여,
벽체 위에 놓인 개구부의 정확한 위치와 너비를 계산하고 벽체를 분할합니다.
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from pydantic import BaseModel, Field

from neuro_seq_cad.geometry.primitives import Point2D, Line2D, BBox2D
from neuro_seq_cad.detection.symbol_schema import SymbolDetection

logger = logging.getLogger(__name__)


class OpeningInfo(BaseModel):
    """벽체 위에 매핑된 개구부 정보 (문, 창문 등)."""

    id: str = Field(default_factory=lambda: f"OPN-{uuid.uuid4().hex[:6].upper()}")
    type: str  # "door" | "window" | "opening"
    confidence: float = 1.0
    
    # 기하 정보
    center_px: Point2D
    width_px: float
    
    # 벽체 매핑 정보
    wall_index: Optional[int] = None
    t_center: Optional[float] = None  # 벽체 선분 상의 정사영 상대 위치 (0.0 = p1, 1.0 = p2)
    t_start: Optional[float] = None   # 개구부 시작 위치 (t)
    t_end: Optional[float] = None     # 개구부 끝 위치 (t)


def mark_openings(
    walls: List[Line2D],
    detections: List[SymbolDetection],
    max_distance: float = 15.0
) -> List[OpeningInfo]:
    """문/창문 바운딩 박스를 벽체 라인에 매칭하여 개구부 위치를 계산합니다.

    Args:
        walls: 벽체 선분 리스트 (Line2D)
        detections: 검출된 심볼 리스트 (SymbolDetection - 문, 창문 등)
        max_distance: 벽체 선분과 심볼 중심 사이의 최대 허용 수직 거리 (px)

    Returns:
        식별된 개구부 정보 리스트 (OpeningInfo)
    """
    openings: List[OpeningInfo] = []
    
    for det in detections:
        # 문/창문 심볼이 아니면 제외
        if det.type not in ("door", "window", "opening"):
            continue
            
        bbox = BBox2D(x1=det.bbox[0], y1=det.bbox[1], x2=det.bbox[2], y2=det.bbox[3])
        center = bbox.center()
        
        # 가장 가까운 벽체 찾기
        best_wall_idx = -1
        min_dist = float("inf")
        best_t = 0.5
        
        for idx, wall in enumerate(walls):
            dist = wall.point_distance(center)
            if dist < min_dist:
                # 벽체 상에 투영된 파라미터 t 계산 (0=p1, 1=p2)
                t = wall.project_point(center)
                # 벽체 범위 내부(-0.1 ~ 1.1 여유)에 있는 경우만 인정
                if -0.1 <= t <= 1.1:
                    min_dist = dist
                    best_wall_idx = idx
                    best_t = max(0.0, min(1.0, t))
                    
        # 허용 거리 이내인 벽체가 있으면 매칭 적용
        if best_wall_idx != -1 and min_dist <= max_distance:
            wall = walls[best_wall_idx]
            wall_len = wall.length()
            
            if wall_len < 1e-6:
                continue
                
            # 개구부 너비 결정: 벽체 방향에 따른 bbox 치수 선택
            # 수평에 가까운 벽체인 경우 bbox의 가로(width)를 너비로,
            # 수직에 가까운 벽체인 경우 bbox의 세로(height)를 너비로 사용
            dx, dy = wall.direction()
            is_horizontal = abs(dx) > abs(dy)
            
            width_px = bbox.width() if is_horizontal else bbox.height()
            # 너비가 극단적으로 작거나 크면 bbox 대각선이나 max 크기로 fallback
            if width_px < 5.0:
                width_px = max(bbox.width(), bbox.height())
                
            # 벽체 상에서의 t_delta (반너비 비율)
            t_delta = (width_px / 2.0) / wall_len
            t_start = max(0.0, best_t - t_delta)
            t_end = min(1.0, best_t + t_delta)
            
            opn = OpeningInfo(
                type=det.type,
                confidence=det.confidence,
                center_px=center,
                width_px=width_px,
                wall_index=best_wall_idx,
                t_center=best_t,
                t_start=t_start,
                t_end=t_end
            )
            openings.append(opn)
            logger.debug(
                "개구부 매칭 완료: %s -> 벽체 %d (t=%.2f, dist=%.2fpx)",
                det.type, best_wall_idx, best_t, min_dist
            )
            
    return openings


def split_walls_by_openings(
    walls: List[Line2D],
    openings: List[OpeningInfo]
) -> List[Line2D]:
    """벽체 선분을 개구부(문/창문) 영역을 제외하고 분할하여 새로운 벽체 조각 리스트를 만듭니다.

    예: A ───────────── B 벽체에 문 [C, D]가 있다면,
        A ───── C (벽체)  +  C ─── D (문 영역 - 제거)  +  D ───── B (벽체)
        최종적으로 A─C와 D─B 두 개의 선분이 반환됩니다.

    Args:
        walls: 원본 벽체 선분 리스트
        openings: 벽체에 매칭된 개구부 리스트

    Returns:
        개구부 영역이 뚫린 분할된 벽체 선분 리스트
    """
    split_walls: List[Line2D] = []
    
    # 각 벽체에 걸쳐진 개구부들 분류
    walls_openings: List[List[OpeningInfo]] = [[] for _ in range(len(walls))]
    for opn in openings:
        if opn.wall_index is not None and 0 <= opn.wall_index < len(walls):
            walls_openings[opn.wall_index].append(opn)
            
    for idx, wall in enumerate(walls):
        wall_opns = walls_openings[idx]
        
        # 개구부가 없는 벽체는 그대로 유지
        if not wall_opns:
            split_walls.append(wall)
            continue
            
        # 개구부들을 벽체 p1 시작점 기준으로 정렬 (t_start 기준)
        # t_start와 t_end가 유효한지 확인
        valid_opns = [o for o in wall_opns if o.t_start is not None and o.t_end is not None]
        valid_opns.sort(key=lambda o: o.t_start)
        
        # 선분 분할 추적 (벽체 파라미터 t의 구간 [0.0, 1.0]에서 살아남은 구간을 추출)
        current_t = 0.0
        p1, p2 = wall.p1, wall.p2
        
        # 벽체 벡터
        dx = p2.x - p1.x
        dy = p2.y - p1.y
        
        for opn in valid_opns:
            # 개구부 시작 지점까지 벽체가 존재
            if opn.t_start > current_t + 1e-4:
                # 시작점과 끝점 좌표 계산
                seg_p1 = Point2D(x=p1.x + current_t * dx, y=p1.y + current_t * dy)
                seg_p2 = Point2D(x=p1.x + opn.t_start * dx, y=p1.y + opn.t_start * dy)
                # 미세 선분이 아니면 추가
                if seg_p1.distance_to(seg_p2) > 1.0:
                    split_walls.append(Line2D(p1=seg_p1, p2=seg_p2))
                    
            # 개구부 영역을 건너뜀
            current_t = max(current_t, opn.t_end)
            
        # 마지막 개구부 이후 벽체 끝(1.0)까지 남은 구간 처리
        if current_t < 1.0 - 1e-4:
            seg_p1 = Point2D(x=p1.x + current_t * dx, y=p1.y + current_t * dy)
            seg_p2 = p2
            if seg_p1.distance_to(seg_p2) > 1.0:
                split_walls.append(Line2D(p1=seg_p1, p2=seg_p2))
                
    logger.info("개구부 분할 완료: 원본 벽체 %d개 -> 분할 후 %d개", len(walls), len(split_walls))
    return split_walls
