from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from image_to_cad.auto.auto_apply_config import LAYER_ZERO_MIN_CONFIDENCE, PROTECTED_LAYERS
from src.semantics.layer_taxonomy import canonical_layer_name, normalize_layer_name


@dataclass(frozen=True)
class LayerMappingCandidate:
    source_layer: str
    target_layer: str | None
    confidence: float
    object_count: int
    reason: str
    apply_by_default: bool
    blocked_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_layer": self.source_layer,
            "target_layer": self.target_layer,
            "confidence": self.confidence,
            "object_count": self.object_count,
            "reason": self.reason,
            "apply_by_default": self.apply_by_default,
            "blocked_reason": self.blocked_reason,
        }


def guess_layer_mapping(source_layer: str, object_count: int = 0, allow_layer_zero: bool = False) -> LayerMappingCandidate:
    normalized = normalize_layer_name(source_layer)
    if normalized in PROTECTED_LAYERS and not (normalized == "0" and allow_layer_zero):
        return LayerMappingCandidate(source_layer, None, 1.0, object_count, "protected_layer", False, "protected_layer")

    target = canonical_layer_name(source_layer)
    if normalized == "0" and allow_layer_zero:
        target = "ETC"
    if not target:
        return LayerMappingCandidate(source_layer, None, 0.0, object_count, "unknown_layer", False, "unknown_layer")

    confidence, reason = _confidence_for(source_layer, target)
    if normalized == normalize_layer_name(target):
        return LayerMappingCandidate(source_layer, target, 1.0, object_count, "already_standard", False, "already_standard")
    if normalized == "0" and confidence < LAYER_ZERO_MIN_CONFIDENCE:
        return LayerMappingCandidate(source_layer, target, confidence, object_count, reason, False, "layer_zero_requires_high_confidence")
    return LayerMappingCandidate(source_layer, target, confidence, object_count, reason, True)


def build_layer_mapping_candidates(layer_counts: dict[str, int], allow_layer_zero: bool = False) -> list[LayerMappingCandidate]:
    return [
        guess_layer_mapping(layer, count, allow_layer_zero=allow_layer_zero)
        for layer, count in sorted(layer_counts.items(), key=lambda item: item[0].upper())
    ]


def _confidence_for(source_layer: str, target_layer: str) -> tuple[float, str]:
    src = normalize_layer_name(source_layer)
    target = normalize_layer_name(target_layer)
    compact = "".join(ch for ch in src if ch.isalnum())
    if src == target:
        return 1.0, "exact_standard_layer"
    if src == "0":
        return 0.92, "layer_zero_optional"
    if target in src or src in target:
        return 0.95, "strong_name_alias"
    if any(token in compact for token in ("COL", "CONC", "BRCK", "WALL", "TEXT", "HATCH", "HAT", "DIM", "LEAD", "DOOR", "WIN", "PIPE")):
        return 0.92, "known_cad_alias"
    if any(ord(ch) > 127 for ch in source_layer):
        return 0.90, "localized_layer_alias"
    if target in {"ETC", "ETC1", "ETC2", "ETC3", "ETC4"}:
        return 0.72, "fallback_etc_candidate"
    return 0.86, "heuristic_alias"
