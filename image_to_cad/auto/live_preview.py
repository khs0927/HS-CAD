from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from image_to_cad.auto.active_analyzer import ActiveDrawingAnalysis
from image_to_cad.auto.auto_apply_config import LAYER_ZERO_MIN_CONFIDENCE, PROTECTED_LAYERS
from image_to_cad.auto.undo_guard import create_undo_mark, no_save_guard
from src.semantics.layer_taxonomy import normalize_layer_name


@dataclass
class PreviewResult:
    changed: int = 0
    skipped: int = 0
    undo_mark_created: bool = False
    applied_layers: dict[str, int] = field(default_factory=dict)
    skipped_layers: dict[str, str] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed": self.changed,
            "skipped": self.skipped,
            "undo_mark_created": self.undo_mark_created,
            "applied_layers": self.applied_layers,
            "skipped_layers": self.skipped_layers,
            "errors": self.errors,
            "saved": False,
            "mode": "live_preview_no_save",
        }


def apply_live_preview(
    analysis: ActiveDrawingAnalysis,
    *,
    min_confidence: float = 0.82,
    allow_layer_zero: bool = False,
) -> PreviewResult:
    from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter

    adapter = ZWCADCOMAdapter(visible=True, start_if_needed=False)
    adapter.connect()
    doc = adapter.get_active_document()
    result = PreviewResult(undo_mark_created=create_undo_mark(doc))
    candidate_by_layer = {candidate.source_layer: candidate for candidate in analysis.candidates}

    with no_save_guard():
        for obj in doc.ModelSpace:
            try:
                source_layer = str(adapter._safe_get(obj, "Layer", "") or "")
                candidate = candidate_by_layer.get(source_layer)
                if candidate is None or not candidate.target_layer:
                    result.skipped += 1
                    continue
                if not candidate.apply_by_default:
                    result.skipped += 1
                    result.skipped_layers[source_layer] = candidate.blocked_reason or "not_applicable_by_default"
                    continue
                normalized = normalize_layer_name(source_layer)
                if normalized in PROTECTED_LAYERS and not (normalized == "0" and allow_layer_zero):
                    result.skipped += 1
                    result.skipped_layers[source_layer] = "protected_layer"
                    continue
                if normalized == "0" and (not allow_layer_zero or candidate.confidence < LAYER_ZERO_MIN_CONFIDENCE):
                    result.skipped += 1
                    result.skipped_layers[source_layer] = "layer_zero_blocked"
                    continue
                if candidate.confidence < min_confidence:
                    result.skipped += 1
                    result.skipped_layers[source_layer] = "below_min_confidence"
                    continue
                if normalize_layer_name(candidate.target_layer) == normalized:
                    result.skipped += 1
                    result.skipped_layers[source_layer] = "already_standard"
                    continue
                adapter._ensure_layer(candidate.target_layer)
                obj.Layer = candidate.target_layer
                result.changed += 1
                key = f"{source_layer} -> {candidate.target_layer}"
                result.applied_layers[key] = result.applied_layers.get(key, 0) + 1
            except Exception as exc:
                result.errors.append({"error": str(exc)})
        if result.changed:
            adapter._regen()
    return result
