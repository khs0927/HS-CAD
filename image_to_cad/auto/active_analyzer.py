from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from image_to_cad.auto.auto_layer_mapper import LayerMappingCandidate, build_layer_mapping_candidates


@dataclass
class ActiveDrawingAnalysis:
    generated_at: str
    active_doc: str
    object_count: int
    layer_counts: dict[str, int]
    entity_counts: dict[str, int]
    layer_entity_counts: dict[str, dict[str, int]]
    block_counts: dict[str, int]
    text_samples: list[dict[str, Any]]
    dimension_count: int
    candidates: list[LayerMappingCandidate]
    warnings: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "active_doc": self.active_doc,
            "object_count": self.object_count,
            "layer_counts": self.layer_counts,
            "entity_counts": self.entity_counts,
            "layer_entity_counts": self.layer_entity_counts,
            "block_counts": self.block_counts,
            "text_samples": self.text_samples,
            "dimension_count": self.dimension_count,
            "mapping_candidates": [candidate.to_dict() for candidate in self.candidates],
            "warnings": self.warnings,
            "mode": "analysis_only_no_drawing_changes",
        }


def analyze_active_drawing(allow_layer_zero: bool = False, max_text_samples: int = 250) -> ActiveDrawingAnalysis:
    from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter

    adapter = ZWCADCOMAdapter(visible=True, start_if_needed=False)
    adapter.connect()
    doc = adapter.get_active_document()
    active_doc = str(getattr(doc, "FullName", "") or getattr(doc, "Name", ""))
    layer_counts: Counter[str] = Counter()
    entity_counts: Counter[str] = Counter()
    layer_entity_counts: dict[str, Counter[str]] = defaultdict(Counter)
    block_counts: Counter[str] = Counter()
    text_samples: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    object_count = 0
    dimension_count = 0

    for obj in doc.ModelSpace:
        try:
            object_count += 1
            layer = str(adapter._safe_get(obj, "Layer", "<NO_LAYER>") or "<NO_LAYER>")
            object_name = str(adapter._safe_get(obj, "ObjectName", "") or "")
            entity_type = adapter._entity_type(object_name)
            handle = str(adapter._safe_get(obj, "Handle", "") or "")
            layer_counts[layer] += 1
            entity_counts[entity_type] += 1
            layer_entity_counts[layer][entity_type] += 1
            if entity_type == "DIMENSION":
                dimension_count += 1
            if entity_type == "INSERT":
                block_name = str(adapter._safe_get(obj, "EffectiveName", "") or adapter._safe_get(obj, "Name", "") or "")
                if block_name:
                    block_counts[block_name] += 1
            if entity_type in {"TEXT", "MTEXT"} and len(text_samples) < max_text_samples:
                text_samples.append(
                    {
                        "handle": handle,
                        "layer": layer,
                        "text": adapter._safe_get(obj, "TextString"),
                        "style_name": adapter._safe_get(obj, "StyleName"),
                        "height": adapter._safe_get(obj, "Height"),
                    }
                )
        except Exception as exc:
            warnings.append({"stage": "modelspace_scan", "error": str(exc)})

    candidates = build_layer_mapping_candidates(dict(layer_counts), allow_layer_zero=allow_layer_zero)
    return ActiveDrawingAnalysis(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        active_doc=active_doc,
        object_count=object_count,
        layer_counts=dict(layer_counts),
        entity_counts=dict(entity_counts),
        layer_entity_counts={layer: dict(counter) for layer, counter in layer_entity_counts.items()},
        block_counts=dict(block_counts),
        text_samples=text_samples,
        dimension_count=dimension_count,
        candidates=candidates,
        warnings=warnings,
    )
