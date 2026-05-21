DEFAULT_LAYER_BY_ENTITY_TYPE = {
    "wall": "WAL1",
    "masonry_wall": "WAL2",
    "column": "COL",
    "door": "DOOR",
    "window": "WIN",
    "window_frame": "WINBAR",
    "hatch": "WAL_HATCH",
    "raw_line": "RAW_LINES",
    "low_confidence": "AI_LOWCONF",
    "text": "TEXT",
    "dimension": "DIM",
    "leader": "DIMLE",
}


def layer_for_styled_entity(styled_entity: dict) -> tuple[str, str]:
    if styled_entity.get("target_layer"):
        return str(styled_entity["target_layer"]), "styled_result target_layer"
    original = styled_entity.get("original_entity") or {}
    entity_type = str(original.get("entity_type") or "unknown")
    return DEFAULT_LAYER_BY_ENTITY_TYPE.get(entity_type, "QA_MARKUP"), "default entity type fallback"
