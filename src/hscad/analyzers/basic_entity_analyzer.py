"""Basic entity analysis that can run before project-specific analyzers are wired."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from hscad.core.evidence import ConfidenceScore, Evidence, EvidenceKind, EvidenceSource
from hscad.core.models import FileizedDrawing


@dataclass
class BasicEntityAnalysis:
    total_entities: int
    by_type: dict[str, int] = field(default_factory=dict)
    by_layer: dict[str, int] = field(default_factory=dict)
    text_entities: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)

    def to_record(self) -> dict[str, Any]:
        return {
            "total_entities": self.total_entities,
            "by_type": self.by_type,
            "by_layer": self.by_layer,
            "text_entities": self.text_entities,
            "evidence": [item.to_record() for item in self.evidence],
        }


class BasicEntityAnalyzer:
    def analyze(self, drawing: FileizedDrawing) -> BasicEntityAnalysis:
        type_counts = Counter(entity.entity_type for entity in drawing.entities)
        layer_counts = Counter(entity.layer for entity in drawing.entities)
        texts = [
            {"entity_id": entity.entity_id, "layer": entity.layer, "text": entity.text, "geometry": entity.geometry}
            for entity in drawing.entities
            if entity.text
        ]
        evidence: list[Evidence] = [
            Evidence(
                source=EvidenceSource.SYSTEM,
                kind=EvidenceKind.ENTITY,
                payload={"total_entities": len(drawing.entities), "by_type": dict(type_counts), "by_layer": dict(layer_counts)},
                confidence=ConfidenceScore.high("entity counts are deterministic"),
                tags=["analysis", "entity_counts"],
            )
        ]
        for layer, count in layer_counts.items():
            evidence.append(
                Evidence(
                    source=EvidenceSource.SYSTEM,
                    kind=EvidenceKind.LAYER,
                    entity_id=f"layer:{layer}",
                    payload={"layer": layer, "entity_count": count},
                    confidence=ConfidenceScore.high("layer count from parsed entities"),
                    tags=["analysis", "layer"],
                )
            )
        return BasicEntityAnalysis(len(drawing.entities), dict(type_counts), dict(layer_counts), texts, evidence)
