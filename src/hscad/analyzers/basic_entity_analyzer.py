"""Composite analyzer used by main-code pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hscad.analyzers.area_analyzer import AreaAnalyzer, AreaAnalysis
from hscad.analyzers.layer_analyzer import LayerAnalyzer, LayerAnalysis
from hscad.analyzers.spatial_graph_analyzer import SpatialGraphAnalyzer, SpatialGraphAnalysis
from hscad.analyzers.text_role_analyzer import TextRoleAnalyzer, TextRoleAnalysis
from hscad.core.evidence import Evidence, make_evidence
from hscad.core.models import FileizedDrawing


@dataclass(frozen=True)
class CompositeAnalysis:
    layer: LayerAnalysis
    text_roles: TextRoleAnalysis
    areas: AreaAnalysis
    spatial_graph: SpatialGraphAnalysis
    evidence: list[Evidence]

    def to_record(self) -> dict[str, Any]:
        return {
            "layer": self.layer.to_record(),
            "text_roles": self.text_roles.to_record(),
            "areas": self.areas.to_record(),
            "spatial_graph": self.spatial_graph.to_record(),
            "evidence": [e.to_record() for e in self.evidence],
        }


class BasicEntityAnalyzer:
    def analyze(self, drawing: FileizedDrawing) -> CompositeAnalysis:
        layer = LayerAnalyzer().analyze(drawing)
        text_roles = TextRoleAnalyzer().analyze(drawing)
        areas = AreaAnalyzer().analyze(drawing)
        spatial = SpatialGraphAnalyzer().analyze(drawing)
        evidence = [*layer.evidence, *text_roles.evidence, *areas.evidence, *spatial.evidence]
        evidence.append(make_evidence("analyzer.composite.summary", "composite_analysis", "Composite analysis completed", module="hscad.analyzers.basic_entity_analyzer", source_id=drawing.input_path, confidence=0.88 if drawing.entities else 0.3, data={"entity_count": len(drawing.entities)}))
        return CompositeAnalysis(layer, text_roles, areas, spatial, evidence)
