"""Layer semantics analyzer."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from hscad.cad.layer_schema import canonical_layer, layer_role
from hscad.core.evidence import Evidence, make_evidence
from hscad.core.models import FileizedDrawing


@dataclass(frozen=True)
class LayerAnalysis:
    layer_counts: dict[str, int]
    layer_roles: dict[str, str]
    unknown_layers: list[str]
    evidence: list[Evidence]

    def to_record(self) -> dict[str, Any]:
        return {
            "layer_counts": self.layer_counts,
            "layer_roles": self.layer_roles,
            "unknown_layers": self.unknown_layers,
            "evidence": [e.to_record() for e in self.evidence],
        }


class LayerAnalyzer:
    def analyze(self, drawing: FileizedDrawing) -> LayerAnalysis:
        counts: Counter[str] = Counter(canonical_layer(e.layer) for e in drawing.entities)
        roles = {layer: layer_role(layer) for layer in counts}
        unknown = sorted(layer for layer, role in roles.items() if role == "unknown")
        evidence = [make_evidence("analyzer.layer.summary", "layer_semantics", f"Detected {len(counts)} layers", module="hscad.analyzers.layer_analyzer", source_id=drawing.input_path, confidence=0.9 if counts else 0.2, data={"layer_counts": dict(counts), "unknown_layers": unknown})]
        return LayerAnalysis(dict(counts), roles, unknown, evidence)
