"""
polygon_schema.py – Raster2Seq 추론 결과를 위한 Pydantic 스키마.

Raster2Seq 모델이 출력하는 다각형 시퀀스(방, 벽, 문, 창문)를
정형화된 Python 객체로 변환하기 위한 데이터 모델 정의.
"""
from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────
# 다각형 타입 상수
# ──────────────────────────────────────────────────────────────────────
POLYGON_TYPES = frozenset({
    "room",
    "wall_boundary",
    "door",
    "window",
    "unknown",
})

# CubiCasa / S3D / R2G 데이터셋에서 출력되는 라벨 → 정규화된 타입 매핑
LABEL_TO_TYPE: dict[str, str] = {
    # 방 (rooms)
    "Bedroom":       "room",
    "Kitchen":       "room",
    "Bath":          "room",
    "Bathroom":      "room",
    "Living Room":   "room",
    "LivingRoom":    "room",
    "Dining Room":   "room",
    "DiningRoom":    "room",
    "Corridor":      "room",
    "Hallway":       "room",
    "Balcony":       "room",
    "Storage":       "room",
    "Closet":        "room",
    "Garage":        "room",
    "Outdoor":       "room",
    "Room":          "room",
    # 벽 (walls)
    "Wall":          "wall_boundary",
    "wall":          "wall_boundary",
    # 문 (doors)
    "Door":          "door",
    "door":          "door",
    # 창문 (windows)
    "Window":        "window",
    "window":        "window",
}


def _generate_id() -> str:
    """고유 ID를 생성 (UUID v4 앞 8자리)."""
    return uuid.uuid4().hex[:8]


# ──────────────────────────────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────────────────────────────
class PolygonResult(BaseModel):
    """Raster2Seq 모델이 예측한 단일 다각형 결과.

    Attributes:
        id: 고유 식별자 (UUID 기반).
        type: 다각형 종류 – room | wall_boundary | door | window | unknown.
        label: 원본 라벨 (Bedroom, Kitchen, Bath, Door, Window 등).
        points: 꼭짓점 좌표 리스트 [[x, y], ...].  이미지 좌표계 기준.
        confidence: 모델 신뢰도 (0.0 ~ 1.0).
        source: 출처 식별 문자열.
    """

    id: str = Field(default_factory=_generate_id)
    type: str = "unknown"  # room | wall_boundary | door | window | unknown
    label: str = "Unknown"
    points: list[list[float]] = Field(default_factory=list)
    confidence: float = 0.0
    source: str = "raster2seq"

    def num_vertices(self) -> int:
        """꼭짓점 수를 반환."""
        return len(self.points)

    def is_closed(self, tolerance: float = 1.0) -> bool:
        """다각형이 닫혀 있는지 확인 (첫/끝 점 거리 < tolerance)."""
        if len(self.points) < 3:
            return False
        p0, pn = self.points[0], self.points[-1]
        # 유클리드 거리 계산
        dist = ((p0[0] - pn[0]) ** 2 + (p0[1] - pn[1]) ** 2) ** 0.5
        return dist < tolerance

    def bounding_box(self) -> tuple[float, float, float, float]:
        """축 정렬 바운딩 박스를 반환: (x_min, y_min, x_max, y_max).

        꼭짓점이 없으면 (0, 0, 0, 0)을 반환.
        """
        if not self.points:
            return (0.0, 0.0, 0.0, 0.0)
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))


class Raster2SeqOutput(BaseModel):
    """Raster2Seq 추론의 전체 출력.

    하나의 평면도 이미지에 대해 검출된 모든 다각형을 포함한다.
    """

    polygons: list[PolygonResult] = Field(default_factory=list)

    def count_by_type(self) -> dict[str, int]:
        """타입별 다각형 개수를 딕셔너리로 반환."""
        counts: dict[str, int] = {}
        for poly in self.polygons:
            counts[poly.type] = counts.get(poly.type, 0) + 1
        return counts

    @property
    def rooms(self) -> list[PolygonResult]:
        """방(room) 타입 다각형만 필터링."""
        return [p for p in self.polygons if p.type == "room"]

    @property
    def walls(self) -> list[PolygonResult]:
        """벽(wall_boundary) 타입 다각형만 필터링."""
        return [p for p in self.polygons if p.type == "wall_boundary"]

    @property
    def doors(self) -> list[PolygonResult]:
        """문(door) 타입 다각형만 필터링."""
        return [p for p in self.polygons if p.type == "door"]

    @property
    def windows(self) -> list[PolygonResult]:
        """창문(window) 타입 다각형만 필터링."""
        return [p for p in self.polygons if p.type == "window"]
