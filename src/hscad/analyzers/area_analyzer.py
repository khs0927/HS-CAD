"""Area extraction based on closed lightweight polylines."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hscad.analyzers.geometry_utils import polygon_area
from hscad.cad.layer_schema import layer_role
from hscad.core.evidence import Evidence, make_evidence
from hscad.core.models import FileizedDrawing


@dataclass(frozen=True)
class AreaElement:
    entity_id: str
    layer: str
    area: float
    unit: str = "drawing_unit^2"

    def to_record(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class AreaAnalysis:
    areas: list[AreaElement]
    total_area: float
    evidence: list[Evidence]

    def to_record(self) -> dict[str, Any]:
        return {"areas": [a.to_record() for a in self.areas], "total_area": self.total_area, "evidence": [e.to_record() for e in self.evidence]}


class AreaAnalyzer:
    def analyze(self, drawing: FileizedDrawing) -> AreaAnalysis:
        areas: list[AreaElement] = []
        for ent in drawing.entities:
            if ent.entity_type.upper() in {"LWPOLYLINE", "POLYLINE"} and (ent.geometry.get("closed") or len(ent.points) >= 4):
                area = polygon_area(ent.points)
                if area > 0:
                    areas.append(AreaElement(ent.entity_id, ent.layer, area))
        total = sum(a.area for a in areas)
        evidence = [make_evidence("analyzer.area.summary", "area_extraction", f"Extracted {len(areas)} closed area candidates", module="hscad.analyzers.area_analyzer", source_id=drawing.input_path, confidence=0.82 if areas else 0.3, data={"total_area": total, "area_count": len(areas)})]
        return AreaAnalysis(areas, total, evidence)
