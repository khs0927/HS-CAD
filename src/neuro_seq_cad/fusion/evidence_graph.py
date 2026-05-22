"""
fusion.evidence_graph – 다중 소스 증거 그래프 (Multi-Source Evidence Graph)
=========================================================================
Raster2Seq, PlanParser, MLSD, OCR, VLM 등 여러 소스의 검출 결과를
하나의 통합 그래프로 합치는 핵심 데이터 모델.

각 EvidenceEntity 는 하나의 건축 요소(벽, 문, 창, 텍스트 등)를 나타내며,
검출 소스, 좌표, 신뢰도, 관계 정보를 모두 포함한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class SourceInfo(BaseModel):
    """검출 소스 정보 — 어떤 모델/파이프라인이 이 엔티티를 만들었는지 기록."""
    name: str = Field(..., description="Source model name (raster2seq, planparser, mlsd, ocr, vlm)")
    version: str = Field("", description="Model or pipeline version string")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Source-specific confidence")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extra source-specific info")


class Polygon2D(BaseModel):
    """2D 폴리곤 좌표 (이미지 좌표계, top-left origin, y-down)."""
    points: list[list[float]] = Field(default_factory=list, description="[[x,y], ...] vertices")
    closed: bool = Field(True, description="Whether polygon is closed")


class BBox(BaseModel):
    """Axis-aligned bounding box (이미지 좌표계)."""
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0

    @property
    def width(self) -> float:
        return abs(self.x2 - self.x1)

    @property
    def height(self) -> float:
        return abs(self.y2 - self.y1)

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    def as_list(self) -> list[float]:
        return [self.x1, self.y1, self.x2, self.y2]


class Relation(BaseModel):
    """엔티티 간 관계 (벽–문 연결, 벽–벽 교차 등)."""
    target_id: str = Field(..., description="Connected entity ID")
    relation_type: str = Field("connected", description="connected|intersects|contains|adjacent")
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceEntity(BaseModel):
    """
    하나의 건축 요소에 대한 증거 엔티티.

    이미지 좌표계(top-left origin, y-down)로 저장되며,
    CAD 좌표 변환은 DXFBuilder 에서 수행한다.
    """
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    entity_type: str = Field(..., description="wall|door|window|column|room|text|dimension|stair|furniture|unknown")
    subtype: str = Field("", description="e.g. masonry, sliding_door, fixed_window ...")

    # ── 기하 정보 (이미지 좌표계) ──
    bbox: BBox | None = Field(None, description="Bounding box (이미지 좌표)")
    polygon: Polygon2D | None = Field(None, description="Outline polygon (벽체/방 경계)")
    points: list[list[float]] = Field(default_factory=list, description="Line endpoints [[x1,y1,x2,y2], ...]")
    angle: float = Field(0.0, description="Rotation angle in degrees")

    # ── 텍스트 / 치수 ──
    text: str = Field("", description="OCR text content or dimension label")
    text_height: float = Field(250.0, description="Text height in CAD units (mm)")

    # ── 소스 및 신뢰도 ──
    sources: list[SourceInfo] = Field(default_factory=list)
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Fused confidence score")
    needs_review: bool = Field(False)

    # ── 관계 ──
    relations: list[Relation] = Field(default_factory=list)

    # ── 확장 메타데이터 ──
    metadata: dict[str, Any] = Field(default_factory=dict)

    # ── 레이어 힌트 (CAD 변환용) ──
    layer_hint: str = Field("", description="Target CAD layer if pre-determined")

    def add_source(self, name: str, confidence: float = 1.0, **kwargs: Any) -> None:
        """소스 정보를 추가하고 전체 신뢰도를 재계산한다."""
        self.sources.append(SourceInfo(name=name, confidence=confidence, metadata=kwargs))
        # 가중 평균으로 전체 신뢰도 갱신 (소스가 많을수록 신뢰도 상승)
        if self.sources:
            self.confidence = sum(s.confidence for s in self.sources) / len(self.sources)

    def resolve_layer(self) -> str:
        """entity_type → 표준 CAD 레이어 이름 매핑."""
        if self.layer_hint:
            return self.layer_hint
        _MAP: dict[str, str] = {
            "wall": "WAL1",
            "door": "DOOR",
            "window": "WIN",
            "column": "COL",
            "room": "ZONE",
            "text": "TXT",
            "dimension": "DIM",
            "stair": "STAIR",
            "furniture": "FUR",
        }
        return _MAP.get(self.entity_type, "QA-REVIEW")


class PipelineMeta(BaseModel):
    """파이프라인 실행 메타데이터."""
    pipeline_version: str = "0.1.0"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    image_path: str = ""
    image_width: int = 0
    image_height: int = 0
    scale_pixels_per_mm: float = 1.0
    active_sources: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EvidenceGraph(BaseModel):
    """
    다중 소스 증거 그래프 — 파이프라인 전체의 통합 결과물.

    모든 모듈(CAD builder, VLM refiner, QA reviewer 등)은
    이 그래프를 입력으로 받아 처리한다.
    """
    version: str = "1.0"
    entities: list[EvidenceEntity] = Field(default_factory=list)
    pipeline: PipelineMeta = Field(default_factory=PipelineMeta)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # ── 편의 메서드 ──

    def by_type(self, entity_type: str) -> list[EvidenceEntity]:
        """특정 타입의 엔티티만 필터링."""
        return [e for e in self.entities if e.entity_type == entity_type]

    def by_id(self, entity_id: str) -> EvidenceEntity | None:
        """ID로 엔티티 검색."""
        for e in self.entities:
            if e.id == entity_id:
                return e
        return None

    def low_confidence(self, threshold: float = 0.5) -> list[EvidenceEntity]:
        """신뢰도가 낮은 엔티티들 반환."""
        return [e for e in self.entities if e.confidence < threshold]

    def summary(self) -> dict[str, int]:
        """엔티티 타입별 개수 요약."""
        counts: dict[str, int] = {}
        for e in self.entities:
            counts[e.entity_type] = counts.get(e.entity_type, 0) + 1
        return counts
