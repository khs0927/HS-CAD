"""Canonical HS-CAD layer schema."""
from __future__ import annotations

LAYER_SCHEMA: dict[str, str] = {
    "COL": "structural columns, concrete/steel columns, structural walls",
    "WAL1": "lightweight partition walls",
    "WAL2": "masonry walls",
    "WAL3": "variant or unknown wall group",
    "WAL_HATCH": "wall hatch or filled wall region",
    "DOOR": "door leaf and frame",
    "DOOR_SWING": "door swing arc",
    "WIN": "window object",
    "WINBAR": "window frame/bar",
    "WINELE": "window elevation line",
    "STAIR": "stair elements",
    "DIM": "dimension entities",
    "DIMLE": "dimension leaders and notes",
    "CEN": "main column centerline",
    "CEN1": "secondary centerline",
    "ELE": "elevation lines",
    "TEXT": "general text",
    "FURN": "furniture and equipment",
    "RAW_LINES": "unclassified raw extracted lines",
    "AI_LOWCONF": "low confidence AI results",
    "QA_MARKUP": "manual review and warning overlays",
}

STRUCTURAL_LAYERS = {"COL", "CEN", "CEN1"}
WALL_LAYERS = {"WAL1", "WAL2", "WAL3", "WAL_HATCH"}
OPENING_LAYERS = {"DOOR", "DOOR_SWING", "WIN", "WINBAR", "WINELE"}
QA_LAYERS = {"RAW_LINES", "AI_LOWCONF", "QA_MARKUP"}


def canonical_layer(layer: str | None) -> str:
    if not layer:
        return "0"
    candidate = str(layer).strip().upper()
    return candidate if candidate in LAYER_SCHEMA else candidate


def layer_role(layer: str | None) -> str:
    layer = canonical_layer(layer)
    if layer in STRUCTURAL_LAYERS:
        return "structural"
    if layer in WALL_LAYERS:
        return "wall"
    if layer in OPENING_LAYERS:
        return "opening"
    if layer in QA_LAYERS:
        return "qa"
    if layer in {"TEXT", "DIM", "DIMLE", "ELE"}:
        return "annotation"
    return "unknown"
