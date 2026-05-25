from __future__ import annotations

from typing import Any

from src.analysis.dxf_delta_extractor import DXFDeltaReport


def validate_signature(seed: dict[str, Any], delta: DXFDeltaReport) -> dict[str, Any]:
    """
    Compares a theoretical Signature Seed (from config rules) against
    the empirical DXFDeltaReport (from live sandbox execution).
    """
    alias = seed.get("alias", "unknown")
    
    if delta.added_count == 0 and delta.modified_count == 0 and delta.deleted_count == 0:
        return {
            "alias": alias,
            "status": "failed",
            "reason": "Sandbox delta is completely empty. Command did not execute or failed.",
        }
        
    hint = seed.get("signature_hint", {})
    expected_layers = hint.get("expected_layer_names", [])
    expected_types = hint.get("expected_added_types", [])
    
    added_layers = {str(ent.get("layer", "")) for ent in delta.added}
    added_types = {str(ent.get("entity_type", "")) for ent in delta.added}
    
    # Heuristic match
    layer_match = bool(added_layers & set(expected_layers)) if expected_layers else True
    type_match = bool(added_types & set(expected_types)) if expected_types else True
    
    # If the command modifies existing geometry instead of adding (like trims for doors)
    is_modifier_cmd = "block_or_arc_insert" in str(hint.get("geometry_patterns", []))
    if is_modifier_cmd and delta.modified_count > 0:
        type_match = True  # It's okay if it just modified things
        
    if layer_match and type_match:
        return {
            "alias": alias,
            "status": "verified",
            "evidence": {
                "matched_layers": list(added_layers),
                "matched_types": list(added_types),
                "added_count": delta.added_count,
                "modified_count": delta.modified_count,
            }
        }
    else:
        return {
            "alias": alias,
            "status": "failed",
            "reason": f"Heuristic mismatch. Expected layers: {expected_layers}, Got: {added_layers}. Expected types: {expected_types}, Got: {added_types}",
        }
