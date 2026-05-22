"""
primitives — 기본 기하 요소 (Point, Line, Polygon, BBox)

모든 좌표는 이미지 좌표계(좌상단 원점, y-down) 기준이다.
CAD 좌표로 변환할 때는 cad_y = (img_height - img_y) * scale 적용.
"""

from __future__ import annotations

import math
from typing import Self

from pydantic import BaseModel, Field, model_validator


# ──────────────────────────────────────────────
# Point2D — 2차원 점
# ──────────────────────────────────────────────
class Point2D(BaseModel):
    """2-D point (immutable value object)."""

    x: float
    y: float

    # ── 연산 helpers ──────────────────────────
    def distance_to(self, other: Point2D) -> float:
        """두 점 사이의 유클리드 거리를 반환한다."""
        return math.hypot(self.x - other.x, self.y - other.y)

    def midpoint_to(self, other: Point2D) -> Point2D:
        """두 점의 중점을 반환한다."""
        return Point2D(x=(self.x + other.x) / 2.0, y=(self.y + other.y) / 2.0)

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)

    def translate(self, dx: float, dy: float) -> Point2D:
        """이동 벡터 (dx, dy)만큼 평행이동한 새 점을 반환한다."""
        return Point2D(x=self.x + dx, y=self.y + dy)

    def rotate_around(self, center: Point2D, angle_rad: float) -> Point2D:
        """center 기준으로 angle_rad 만큼 회전한 새 점을 반환한다."""
        # 중심 기준 상대 좌표
        dx = self.x - center.x
        dy = self.y - center.y
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        # 회전 변환
        new_x = center.x + dx * cos_a - dy * sin_a
        new_y = center.y + dx * sin_a + dy * cos_a
        return Point2D(x=new_x, y=new_y)

    def __hash__(self) -> int:
        return hash((round(self.x, 6), round(self.y, 6)))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Point2D):
            return NotImplemented
        return (round(self.x, 6) == round(other.x, 6) and
                round(self.y, 6) == round(other.y, 6))


# ──────────────────────────────────────────────
# Line2D — 2차원 선분
# ──────────────────────────────────────────────
class Line2D(BaseModel):
    """Directed line segment from *p1* → *p2*."""

    p1: Point2D
    p2: Point2D

    # ── 기하 속성 ─────────────────────────────
    def angle(self) -> float:
        """선분의 각도를 라디안으로 반환 (-π, π]."""
        return math.atan2(self.p2.y - self.p1.y, self.p2.x - self.p1.x)

    def angle_deg(self) -> float:
        """선분의 각도를 도(degree) 단위로 반환 [0, 360)."""
        deg = math.degrees(self.angle())
        return deg % 360.0

    def length(self) -> float:
        """선분의 길이를 반환한다."""
        return self.p1.distance_to(self.p2)

    def midpoint(self) -> Point2D:
        """선분의 중점을 반환한다."""
        return self.p1.midpoint_to(self.p2)

    def direction(self) -> tuple[float, float]:
        """정규화된 방향 벡터를 (dx, dy) 형태로 반환한다."""
        ln = self.length()
        if ln < 1e-12:
            return (0.0, 0.0)
        return (
            (self.p2.x - self.p1.x) / ln,
            (self.p2.y - self.p1.y) / ln,
        )

    def as_tuple(self) -> tuple[float, float, float, float]:
        """(x1, y1, x2, y2) 튜플로 반환한다."""
        return (self.p1.x, self.p1.y, self.p2.x, self.p2.y)

    def reversed(self) -> Line2D:
        """방향이 반대인 새 선분을 반환한다."""
        return Line2D(p1=self.p2, p2=self.p1)

    def point_distance(self, pt: Point2D) -> float:
        """점 pt에서 이 선분(무한 직선 기준)까지의 수직 거리를 반환한다.

        수직 거리 공식:
          d = |( (p2-p1) × (p1-pt) )| / |p2-p1|
        """
        # 외적(2D cross product)으로 부호 있는 거리 계산
        dx = self.p2.x - self.p1.x
        dy = self.p2.y - self.p1.y
        ln = self.length()
        if ln < 1e-12:
            return pt.distance_to(self.p1)
        cross = abs(dx * (self.p1.y - pt.y) - dy * (self.p1.x - pt.x))
        return cross / ln

    def project_point(self, pt: Point2D) -> float:
        """점 pt를 선분 위로 정사영한 파라미터 t를 반환한다 (0=p1, 1=p2)."""
        dx = self.p2.x - self.p1.x
        dy = self.p2.y - self.p1.y
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-12:
            return 0.0
        return ((pt.x - self.p1.x) * dx + (pt.y - self.p1.y) * dy) / len_sq


# ──────────────────────────────────────────────
# Polygon2D — 2차원 다각형 / 폴리라인
# ──────────────────────────────────────────────
class Polygon2D(BaseModel):
    """2-D polygon represented as an ordered list of vertices."""

    points: list[Point2D] = Field(default_factory=list, min_length=0)
    label: str = ""
    is_closed: bool = True

    def area(self) -> float:
        """Shoelace formula로 부호 있는 넓이를 반환한다.

        다각형의 넓이 = 0.5 * |Σ (x_i * y_{i+1} - x_{i+1} * y_i)|
        """
        pts = self.points
        n = len(pts)
        if n < 3:
            return 0.0
        # Shoelace 공식 적용
        s = 0.0
        for i in range(n):
            j = (i + 1) % n
            s += pts[i].x * pts[j].y
            s -= pts[j].x * pts[i].y
        return abs(s) / 2.0

    def signed_area(self) -> float:
        """부호 있는 넓이 — 양이면 CCW, 음이면 CW."""
        pts = self.points
        n = len(pts)
        if n < 3:
            return 0.0
        s = 0.0
        for i in range(n):
            j = (i + 1) % n
            s += pts[i].x * pts[j].y
            s -= pts[j].x * pts[i].y
        return s / 2.0

    def centroid(self) -> Point2D:
        """다각형의 무게중심(centroid)을 반환한다.

        C_x = (1 / 6A) * Σ (x_i + x_{i+1})(x_i * y_{i+1} - x_{i+1} * y_i)
        C_y = (1 / 6A) * Σ (y_i + y_{i+1})(x_i * y_{i+1} - x_{i+1} * y_i)
        """
        pts = self.points
        n = len(pts)
        if n == 0:
            return Point2D(x=0.0, y=0.0)
        if n < 3:
            # 점이 부족하면 단순 평균
            cx = sum(p.x for p in pts) / n
            cy = sum(p.y for p in pts) / n
            return Point2D(x=cx, y=cy)

        a = self.signed_area()
        if abs(a) < 1e-12:
            cx = sum(p.x for p in pts) / n
            cy = sum(p.y for p in pts) / n
            return Point2D(x=cx, y=cy)

        cx = 0.0
        cy = 0.0
        for i in range(n):
            j = (i + 1) % n
            cross = pts[i].x * pts[j].y - pts[j].x * pts[i].y
            cx += (pts[i].x + pts[j].x) * cross
            cy += (pts[i].y + pts[j].y) * cross
        factor = 1.0 / (6.0 * a)
        return Point2D(x=cx * factor, y=cy * factor)

    def perimeter(self) -> float:
        """둘레 길이를 반환한다."""
        pts = self.points
        n = len(pts)
        if n < 2:
            return 0.0
        total = 0.0
        limit = n if self.is_closed else n - 1
        for i in range(limit):
            j = (i + 1) % n
            total += pts[i].distance_to(pts[j])
        return total

    def bounding_box(self) -> BBox2D:
        """외접 바운딩 박스를 반환한다."""
        if not self.points:
            return BBox2D(x1=0, y1=0, x2=0, y2=0)
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return BBox2D(x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys))

    def edges(self) -> list[Line2D]:
        """다각형의 변(edge)을 Line2D 리스트로 반환한다."""
        pts = self.points
        n = len(pts)
        if n < 2:
            return []
        result: list[Line2D] = []
        limit = n if self.is_closed else n - 1
        for i in range(limit):
            j = (i + 1) % n
            result.append(Line2D(p1=pts[i], p2=pts[j]))
        return result


# ──────────────────────────────────────────────
# BBox2D — 축 정렬 바운딩 박스
# ──────────────────────────────────────────────
class BBox2D(BaseModel):
    """Axis-aligned bounding box (x1, y1) = min corner, (x2, y2) = max corner."""

    x1: float
    y1: float
    x2: float
    y2: float

    @model_validator(mode="after")
    def _ensure_order(self) -> Self:
        """좌표 순서를 보정한다 — (x1,y1)이 항상 min, (x2,y2)이 항상 max."""
        if self.x1 > self.x2:
            self.x1, self.x2 = self.x2, self.x1
        if self.y1 > self.y2:
            self.y1, self.y2 = self.y2, self.y1
        return self

    # ── 기하 속성 ─────────────────────────────
    def center(self) -> Point2D:
        """중심점을 반환한다."""
        return Point2D(
            x=(self.x1 + self.x2) / 2.0,
            y=(self.y1 + self.y2) / 2.0,
        )

    def width(self) -> float:
        return self.x2 - self.x1

    def height(self) -> float:
        return self.y2 - self.y1

    def area(self) -> float:
        return self.width() * self.height()

    def contains(self, pt: Point2D) -> bool:
        """점이 박스 내부에 있는지 검사한다."""
        return self.x1 <= pt.x <= self.x2 and self.y1 <= pt.y <= self.y2

    def intersects(self, other: BBox2D) -> bool:
        """두 박스가 겹치는지 검사한다."""
        return not (
            self.x2 < other.x1
            or self.x1 > other.x2
            or self.y2 < other.y1
            or self.y1 > other.y2
        )

    def iou(self, other: BBox2D) -> float:
        """IoU (Intersection over Union)를 반환한다."""
        inter_x1 = max(self.x1, other.x1)
        inter_y1 = max(self.y1, other.y1)
        inter_x2 = min(self.x2, other.x2)
        inter_y2 = min(self.y2, other.y2)
        if inter_x1 >= inter_x2 or inter_y1 >= inter_y2:
            return 0.0
        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        union_area = self.area() + other.area() - inter_area
        if union_area < 1e-12:
            return 0.0
        return inter_area / union_area

    def expand(self, margin: float) -> BBox2D:
        """각 변에서 margin만큼 확장한 새 BBox를 반환한다."""
        return BBox2D(
            x1=self.x1 - margin,
            y1=self.y1 - margin,
            x2=self.x2 + margin,
            y2=self.y2 + margin,
        )

    def as_polygon(self) -> Polygon2D:
        """바운딩 박스를 Polygon2D로 변환한다."""
        return Polygon2D(
            points=[
                Point2D(x=self.x1, y=self.y1),
                Point2D(x=self.x2, y=self.y1),
                Point2D(x=self.x2, y=self.y2),
                Point2D(x=self.x1, y=self.y2),
            ],
            label="bbox",
            is_closed=True,
        )

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)
