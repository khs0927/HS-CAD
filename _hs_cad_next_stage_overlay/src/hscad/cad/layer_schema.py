"""Canonical HS-CAD layer schema."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayerDefinition:
    name: str
    description: str
    role: str
    required: bool = False


LAYER_SCHEMA: dict[str, LayerDefinition] = {
    "COL": LayerDefinition("COL", "structural columns, concrete/steel columns, structural walls", "structure"),
    "WAL1": LayerDefinition("WAL1", "lightweight partition walls", "wall"),
    "WAL2": LayerDefinition("WAL2", "masonry walls", "wall"),
    "WAL3": LayerDefinition("WAL3", "variant or unknown wall group", "wall"),
    "WAL_HATCH": LayerDefinition("WAL_HATCH", "wall hatch or filled wall region", "wall"),
    "DOOR": LayerDefinition("DOOR", "door leaf and frame", "opening"),
    "DOOR_SWING": LayerDefinition("DOOR_SWING", "door swing arc", "opening"),
    "WIN": LayerDefinition("WIN", "window object", "opening"),
    "WINBAR": LayerDefinition("WINBAR", "window frame/bar", "opening"),
    "WINELE": LayerDefinition("WINELE", "window elevation line", "opening"),
    "STAIR": LayerDefinition("STAIR", "stair elements", "circulation"),
    "DIM": LayerDefinition("DIM", "dimension entities", "annotation"),
    "DIMLE": LayerDefinition("DIMLE", "dimension leaders and notes", "annotation"),
    "CEN": LayerDefinition("CEN", "main column centerline", "grid"),
    "CEN1": LayerDefinition("CEN1", "secondary centerline", "grid"),
    "ELE": LayerDefinition("ELE", "elevation lines", "annotation"),
    "TEXT": LayerDefinition("TEXT", "general text", "annotation"),
    "FURN": LayerDefinition("FURN", "furniture and equipment", "equipment"),
    "RAW_LINES": LayerDefinition("RAW_LINES", "unclassified raw extracted lines", "qa", required=True),
    "AI_LOWCONF": LayerDefinition("AI_LOWCONF", "low confidence AI results", "qa", required=True),
    "QA_MARKUP": LayerDefinition("QA_MARKUP", "manual review and warning overlays", "qa", required=True),
}


def layer_names() -> list[str]:
    return list(LAYER_SCHEMA.keys())


def describe_layer(name: str) -> str:
    definition = LAYER_SCHEMA.get(name)
    return definition.description if definition else "unknown layer"


def role_for_layer(name: str) -> str:
    definition = LAYER_SCHEMA.get(name)
    return definition.role if definition else "unknown"
