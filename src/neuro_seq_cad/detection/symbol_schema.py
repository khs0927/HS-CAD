"""
symbol_schema.py – 심볼 검출(Symbol Detection) 결과를 위한 Pydantic 스키마.

PlanParser (YOLO11 + Faster R-CNN) 또는 기타 객체 검출 모델이 출력하는
바운딩 박스 결과를 정형화된 Python 객체로 표현.
"""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────
# 심볼 타입 상수
# ──────────────────────────────────────────────────────────────────────
SYMBOL_TYPES = frozenset({
    "door",
    "window",
    "text",
    "furniture",
    "dimension",
    "stair",
    "elevator",
    "column",
    "unknown",
})

# PlanParser 클래스 이름 → 정규화된 타입 매핑
CLASS_NAME_TO_TYPE: dict[str, str] = {
    "door":       "door",
    "Door":       "door",
    "window":     "window",
    "Window":     "window",
    "text":       "text",
    "Text":       "text",
    "furniture":  "furniture",
    "Furniture":  "furniture",
    "dimension":  "dimension",
    "Dimension":  "dimension",
    "stair":      "stair",
    "Stair":      "stair",
    "elevator":   "elevator",
    "Elevator":   "elevator",
    "column":     "column",
    "Column":     "column",
}


def _generate_id() -> str:
    """고유 ID를 생성 (UUID v4 앞 8자리)."""
    return uuid.uuid4().hex[:8]


# ──────────────────────────────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────────────────────────────
class SymbolDetection(BaseModel):
    """단일 심볼 검출 결과.

    Attributes:
        id: 고유 식별자.
        type: 심볼 종류 – door | window | text | furniture | dimension | unknown.
        bbox: 바운딩 박스 [x1, y1, x2, y2].  이미지 좌표계 기준.
        confidence: 검출 신뢰도 (0.0 ~ 1.0).
        source: 검출 모델/서비스 출처 ("planparser", "yolo", etc.).
        class_name: 모델이 출력한 원시 클래스 이름.
    """

    id: str = Field(default_factory=_generate_id)
    type: str = "unknown"
    bbox: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    confidence: float = 0.0
    source: str = "planparser"
    class_name: str = ""

    @property
    def width(self) -> float:
        """바운딩 박스 너비."""
        if len(self.bbox) >= 4:
            return abs(self.bbox[2] - self.bbox[0])
        return 0.0

    @property
    def height(self) -> float:
        """바운딩 박스 높이."""
        if len(self.bbox) >= 4:
            return abs(self.bbox[3] - self.bbox[1])
        return 0.0

    @property
    def area(self) -> float:
        """바운딩 박스 면적."""
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        """바운딩 박스 중심점 (cx, cy)."""
        if len(self.bbox) >= 4:
            cx = (self.bbox[0] + self.bbox[2]) / 2.0
            cy = (self.bbox[1] + self.bbox[3]) / 2.0
            return (cx, cy)
        return (0.0, 0.0)

    @classmethod
    def from_planparser_dict(cls, det: dict[str, Any]) -> "SymbolDetection":
        """PlanParser API 응답 딕셔너리로부터 인스턴스 생성.

        기대 형식:
          {"class": "door", "confidence": 0.92, "bbox": [x1, y1, x2, y2]}
        """
        class_name = str(det.get("class", det.get("class_name", "unknown")))
        det_type = CLASS_NAME_TO_TYPE.get(class_name, "unknown")
        raw_bbox = det.get("bbox", [0.0, 0.0, 0.0, 0.0])
        bbox = [float(v) for v in raw_bbox[:4]]
        confidence = float(det.get("confidence", det.get("score", 0.0)))

        return cls(
            type=det_type,
            bbox=bbox,
            confidence=confidence,
            source="planparser",
            class_name=class_name,
        )


class DetectionOutput(BaseModel):
    """심볼 검출의 전체 출력.

    하나의 이미지에 대해 검출된 모든 심볼을 포함한다.
    """

    symbols: list[SymbolDetection] = Field(default_factory=list)

    def count_by_type(self) -> dict[str, int]:
        """타입별 검출 수를 딕셔너리로 반환."""
        counts: dict[str, int] = {}
        for sym in self.symbols:
            counts[sym.type] = counts.get(sym.type, 0) + 1
        return counts

    def filter_by_type(self, symbol_type: str) -> list[SymbolDetection]:
        """특정 타입의 검출 결과만 필터링."""
        return [s for s in self.symbols if s.type == symbol_type]

    def filter_by_confidence(self, threshold: float = 0.5) -> "DetectionOutput":
        """신뢰도 임계값 이상의 결과만 필터링하여 새 DetectionOutput 반환."""
        filtered = [s for s in self.symbols if s.confidence >= threshold]
        return DetectionOutput(symbols=filtered)

    @property
    def doors(self) -> list[SymbolDetection]:
        return self.filter_by_type("door")

    @property
    def windows(self) -> list[SymbolDetection]:
        return self.filter_by_type("window")

    @property
    def texts(self) -> list[SymbolDetection]:
        return self.filter_by_type("text")

    @property
    def furniture(self) -> list[SymbolDetection]:
        return self.filter_by_type("furniture")
