from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class LayerRule:
    layer: str
    category: str
    role: str
    description: str
    structural: bool = False
    material: str | None = None
    color_index: int | None = None
    visible: bool = True
    confidence: float = 0.98
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# User drafting standard. This table is the primary source of truth for object
# semantics. Geometry, block names, text, and screenshots only refine or support
# this layer-first classification.
_BASE_RULES: dict[str, LayerRule] = {
    "COL": LayerRule("COL", "structure", "structural_member", "Structural columns, concrete walls, steel walls, and steel beams", True, "concrete_or_steel"),
    "WAL1": LayerRule("WAL1", "wall", "lightweight_wall", "Non-structural wall, white lightweight wall", False, "lightweight", color_index=7),
    "WAL2": LayerRule("WAL2", "wall", "masonry_wall", "Non-structural wall, green masonry wall", False, "masonry", color_index=3),
    "WAL3": LayerRule("WAL3", "wall", "nonstructural_wall", "Other non-structural wall", False, "nonstructural"),
    "DOOR": LayerRule("DOOR", "opening", "door_plan", "Door objects in plan"),
    "DOOR_ELE": LayerRule("DOOR_ELE", "elevation", "door_elevation", "Door elevation linework"),
    "WIN": LayerRule("WIN", "opening", "window_plan", "Window objects in plan"),
    "WINBAR": LayerRule("WINBAR", "opening", "window_frame", "Window frame or bar"),
    "WINELE": LayerRule("WINELE", "elevation", "window_elevation", "Window elevation linework"),
    "STAIR": LayerRule("STAIR", "vertical_circulation", "stair", "Stair objects"),
    "DIM": LayerRule("DIM", "annotation", "dimension", "Dimension lines and dimension text"),
    "DIMLE": LayerRule("DIMLE", "annotation", "leader", "Leader lines"),
    "CEN": LayerRule("CEN", "grid_centerline", "main_column_centerline", "Main column centerline"),
    "CEN1": LayerRule("CEN1", "grid_centerline", "wall_aux_centerline", "Auxiliary centerline for lightweight walls or wall centerlines"),
    "CEN2": LayerRule("CEN2", "grid_centerline", "other_aux_centerline", "Other auxiliary centerline"),
    "DEFPOINTS": LayerRule("DEFPOINTS", "guide", "nonplot_guide", "Non-plot guide layer", visible=False, confidence=1.0),
    "FIX": LayerRule("FIX", "fixture", "built_in_fixture", "Built-in furniture, bathroom fixtures, kitchen fixtures"),
    "FUR": LayerRule("FUR", "furniture", "loose_furniture", "General furniture"),
    "SYM": LayerRule("SYM", "symbol", "symbol_line", "Symbol linework"),
    "SYM_T": LayerRule("SYM_T", "symbol", "symbol_text", "Symbol text"),
    "TIT": LayerRule("TIT", "title", "title_text", "Title and drawing text"),
    "AREA": LayerRule("AREA", "site_boundary", "cadastral_line", "Site or cadastral boundary line"),
    "PARKING": LayerRule("PARKING", "parking", "parking_line", "Parking linework"),
    "INS": LayerRule("INS", "insulation", "insulation", "Insulation linework"),
    "BOUND": LayerRule("BOUND", "boundary", "zone_boundary", "Zone or area boundary"),
    "A-FORM": LayerRule("A-FORM", "sheet", "drawing_border", "Drawing border or form"),
    "MARK": LayerRule("MARK", "coordination", "shared_mark", "Shared coordination mark"),
}

_ELE_COLORS = {"ELE": 8, "ELE1": 251, "ELE2": 252, "ELE3": 253, "ELE4": 254}
for name, color in _ELE_COLORS.items():
    _BASE_RULES[name] = LayerRule(name, "elevation", "elevation_line", f"Elevation linework, color {color}", color_index=color)
for name, color in _ELE_COLORS.items():
    etc_name = name.replace("ELE", "ETC", 1)
    _BASE_RULES[etc_name] = LayerRule(etc_name, "etc_elevation", "etc_line", f"Other linework following {name} color rule", color_index=color)


def normalize_layer_name(layer: str | None) -> str:
    return str(layer or "").strip().upper()


def get_layer_rule(layer: str | None) -> LayerRule | None:
    name = normalize_layer_name(layer)
    if name in _BASE_RULES:
        return _BASE_RULES[name]
    if name.startswith("WAL") and name[3:].isdigit():
        return LayerRule(name, "wall", "nonstructural_wall_variant", f"Non-structural wall variant layer {name}", False, "nonstructural", confidence=0.86)
    if name.startswith("ELE") and (name == "ELE" or name[3:].isdigit()):
        return LayerRule(name, "elevation", "elevation_line_variant", f"Elevation variant layer {name}", color_index=None, confidence=0.76)
    if name.startswith("ETC") and (name == "ETC" or name[3:].isdigit()):
        return LayerRule(name, "etc_elevation", "etc_line_variant", f"Other elevation-style variant layer {name}", color_index=None, confidence=0.74)
    return None


def classify_layer(layer: str | None, color: Any = None) -> dict[str, Any]:
    rule = get_layer_rule(layer)
    if rule is None:
        return {
            "layer": str(layer or ""),
            "category": "unknown",
            "role": "unknown",
            "description": "Layer is not defined in the architectural taxonomy. Use geometry, block name, text, and optional screen capture as supporting evidence.",
            "structural": False,
            "material": None,
            "expected_color_index": None,
            "actual_color": color,
            "color_matches_rule": None,
            "visible": True,
            "confidence": 0.2,
            "notes": "no_layer_rule",
        }
    expected = rule.color_index
    actual_int = _try_int_color(color)
    return {
        "layer": normalize_layer_name(layer),
        "category": rule.category,
        "role": rule.role,
        "description": rule.description,
        "structural": rule.structural,
        "material": rule.material,
        "expected_color_index": expected,
        "actual_color": color,
        "color_matches_rule": None if expected is None or actual_int is None else actual_int == expected,
        "visible": rule.visible,
        "confidence": rule.confidence,
        "notes": rule.notes,
    }


def layer_rules_as_rows() -> list[dict[str, Any]]:
    return [rule.to_dict() for _, rule in sorted(_BASE_RULES.items())]


def _try_int_color(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None
