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
    linetype: str = "CONTINUOUS"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_BASE_RULES: dict[str, LayerRule] = {
    "COL": LayerRule("COL", "structure", "structural_member", "Structural frame", structural=True, material="concrete_or_steel"),
    "WAL1": LayerRule("WAL1", "wall", "lightweight_wall", "Lightweight wall", material="lightweight", color_index=7),
    "WAL2": LayerRule("WAL2", "wall", "masonry_wall", "Masonry wall", material="masonry", color_index=3),
    "WAL3": LayerRule("WAL3", "wall", "nonstructural_wall", "Other wall", material="nonstructural"),
    "DOOR": LayerRule("DOOR", "opening", "door_plan", "Door plan"),
    "DOOR_ELE": LayerRule("DOOR_ELE", "elevation", "door_elevation", "Door elevation"),
    "WIN": LayerRule("WIN", "opening", "window_plan", "Window plan"),
    "WINBAR": LayerRule("WINBAR", "opening", "window_frame", "Window frame or bar"),
    "WINELE": LayerRule("WINELE", "elevation", "window_elevation", "Window elevation"),
    "HAT": LayerRule("HAT", "hatch", "hatch_pattern", "Hatch linework"),
    "HID": LayerRule("HID", "hidden_line", "hidden_dashed_line", "Hidden dashed line", linetype="HID"),
    "ZONE": LayerRule("ZONE", "zone", "zone_boundary", "Zone boundary"),
    "SEC1": LayerRule("SEC1", "section", "section_line_primary", "Section line"),
    "SEC2": LayerRule("SEC2", "section", "section_line_secondary", "Section line"),
    "FIN1": LayerRule("FIN1", "finish", "finish_line_primary", "Finish line"),
    "FIN2": LayerRule("FIN2", "finish", "finish_line_secondary", "Finish line"),
    "TXT": LayerRule("TXT", "annotation", "text", "General text"),
    "TXT1": LayerRule("TXT1", "annotation", "extra_text", "Other text or description"),
    "TXT2": LayerRule("TXT2", "annotation", "extra_text", "Other text or description"),
    "MEP": LayerRule("MEP", "mep", "mep_linework", "MEP linework"),
    "NOTE": LayerRule("NOTE", "annotation", "note", "Notes and explanations"),
    "STAIR": LayerRule("STAIR", "vertical_circulation", "stair", "Stair objects"),
    "DIM": LayerRule("DIM", "annotation", "dimension", "Dimensions"),
    "DIMLE": LayerRule("DIMLE", "annotation", "leader", "Leader lines"),
    "CEN": LayerRule("CEN", "grid_centerline", "main_column_centerline", "Main centerline", linetype="CENTER"),
    "CEN1": LayerRule("CEN1", "grid_centerline", "structural_centerline", "Structural centerline", linetype="CENTER"),
    "CEN2": LayerRule("CEN2", "grid_centerline", "other_centerline", "Other centerline", linetype="CENTER2"),
    "CEN3": LayerRule("CEN3", "grid_centerline", "other_centerline", "Other centerline", linetype="CENTER2"),
    "DEFPOINTS": LayerRule("DEFPOINTS", "guide", "nonplot_guide", "Non-plot guide layer", visible=False, confidence=1.0),
    "FIX": LayerRule("FIX", "fixture", "built_in_fixture", "Built-in fixtures"),
    "FUR": LayerRule("FUR", "furniture", "loose_furniture", "Furniture"),
    "SYM": LayerRule("SYM", "symbol", "symbol_line", "Symbols"),
    "SYM_T": LayerRule("SYM_T", "symbol", "symbol_text", "Symbol text"),
    "TIT": LayerRule("TIT", "title", "title_text", "Title text"),
    "AREA": LayerRule("AREA", "site_boundary", "cadastral_line", "Site boundary"),
    "PARKING": LayerRule("PARKING", "parking", "parking_line", "Parking linework"),
    "INS": LayerRule("INS", "insulation", "insulation", "Insulation batting", linetype="BATTING"),
    "BOUND": LayerRule("BOUND", "boundary", "zone_boundary", "Boundary"),
    "A-FORM": LayerRule("A-FORM", "sheet", "drawing_border", "Drawing border"),
    "MARK": LayerRule("MARK", "coordination", "shared_mark", "Coordination mark"),
    "GRID": LayerRule("GRID", "grid", "axis_grid", "Grid or axis lines", linetype="CENTER"),
    "GRID_BUB": LayerRule("GRID_BUB", "grid", "axis_grid_bubble", "Grid bubble symbols"),
}

_ELE_COLORS = {"ELE": 8, "ELE1": 251, "ELE2": 252, "ELE3": 253, "ELE4": 254}
for name, color in _ELE_COLORS.items():
    _BASE_RULES[name] = LayerRule(name, "elevation", "elevation_line", f"Elevation linework, color {color}", color_index=color)
for name, color in _ELE_COLORS.items():
    etc_name = name.replace("ELE", "ETC", 1)
    _BASE_RULES[etc_name] = LayerRule(etc_name, "etc_elevation", "etc_line", f"Other linework following {name} color rule", color_index=color)


def normalize_layer_name(layer: str | None) -> str:
    return str(layer or "").strip().upper()


def _compact_layer_name(name: str) -> str:
    return "".join(ch for ch in name if ch.isalnum())


def _has(value: str, *tokens: str) -> bool:
    return any(token in value for token in tokens)


def canonical_layer_name(layer: str | None) -> str | None:
    name = normalize_layer_name(layer)
    compact = _compact_layer_name(name)
    raw = str(layer or "").strip()

    if name in _BASE_RULES:
        return name
    if name in {"0", "_0"}:
        return "ETC"
    if name == "DOORELE":
        return "DOOR_ELE"
    if name.startswith("DOOR") or "TOLDOOR" in compact or "TOLSWING" in compact or "\ubb38\ud2c0" in raw:
        return "DOOR"
    if name == "WID" or name.startswith("WIN") or "\ucc3d\ud638" in raw:
        if "BAR" in compact:
            return "WINBAR"
        if "ELE" in compact:
            return "WINELE"
        return "WIN"
    if _has(raw, "\uad6c\uc5ed\uacc4"):
        return "ZONE"
    if _has(raw, "\uace8\uc870", "\ucf58\ud06c\ub9ac\ud2b8") or "COL" in compact or "CONC" in compact or "STEELBEAM" in compact:
        return "COL"
    if _has(raw, "\uc870\uc801") or name in {"WALL2", "WAL2"} or "BRCK" in compact:
        return "WAL2"
    if name == "WALL3":
        return "WAL3"
    if name in {"WAL", "WALL1"} or name.startswith("@WALL"):
        return "WAL1"
    if _has(raw, "\ub2e8\uba74") or "SECTION" in compact or "SEC" in compact:
        return "SEC2" if "2" in compact else "SEC1"
    if _has(raw, "\ub9c8\uac10\uc1202", "\ub9c8\uac10\uc1203", "@\ub9c8\uac102") or "FIN2" in compact or "FIN3" in compact or "FIN4" in compact:
        return "FIN2"
    if _has(raw, "\ub9c8\uac10", "\ub9c8\uac10\uc120") or "FIN" in compact or "FNSH" in compact:
        return "FIN1"
    if _has(raw, "\uc124\uba85") or "LEVEL" in compact or "\ub808\ubca8" in raw:
        return "NOTE"
    if _has(raw, "\ubd80\ud638", "\ubc29\uc704\ud45c") or name.startswith("SYM") or compact.endswith("SYM") or "SYMBOL" in compact or "TAG" in compact:
        return "SYM"
    if _has(raw, "\ubb38\uc790-\uae30\ud0c0"):
        return "TXT1"
    if _has(raw, "\ubb38\uc790", "\uae00\uc790", "\uc2e4\uba85") or name.startswith("@TEXT") or name.startswith("TEXT") or name.startswith("TXT") or compact.endswith("TEXT"):
        return "TXT"
    if _has(raw, "\uc124\ube44") or name == "MEP" or "PIPE" in compact:
        return "MEP"
    if name in {"INSU", "INSUL"} or name.startswith("@INS") or _has(raw, "\ub2e8\uc5f4"):
        return "INS"
    if _has(raw, "\uc810\uc120") or name.startswith("HID"):
        return "HID"
    if _has(raw, "\ud574\uce58") or name == "HA" or name.startswith("HAT") or compact.endswith("HAT") or "HATCH" in compact:
        return "HAT"
    if _has(raw, "\uc911\uc2ec\uc120") or name == "CENTER" or name.startswith("CEN") or compact.endswith("CNTL"):
        return "CEN2"
    if name.startswith("@ELE") or name.startswith("ELEV") or name.startswith("EL") or name.startswith("A-ELE") or name.startswith("ELE"):
        return "ELE1"
    if name.startswith("DIM") or name.endswith("DIM") or "DIM" in compact:
        return "DIM"
    if name == "LEADER" or "LEAD" in compact:
        return "DIMLE"
    if compact.endswith("FUR") or "FURN" in compact:
        return "FUR"
    if name.startswith("FIX") or "SANT" in compact or "SAN" == compact:
        return "FIX"
    if name == "ST" or name.startswith("STAIR"):
        return "STAIR"
    if name == "GRID" or "AXIS" in compact:
        return "GRID"
    if name == "GRID_BUB":
        return "GRID_BUB"
    if name in {"FORM", "PAPER"} or "\ub3c4\uacfd" in raw:
        return "A-FORM"
    if name == "BOUND" or "\uacbd\uacc4" in raw or "\ud14c\ub450\ub9ac" in raw:
        return "BOUND"
    if name == "TITLE":
        return "TIT"
    if "TREE" in compact or "\ub098\ubb34" in raw:
        return "ETC"
    if "LINE" in compact or name in {"L1", "L2", "8", "TEXT_LAYER", "TC-2"}:
        return "ETC"
    return None


def get_layer_rule(layer: str | None) -> LayerRule | None:
    canonical = canonical_layer_name(layer)
    if canonical in _BASE_RULES:
        return _BASE_RULES[canonical]
    name = normalize_layer_name(layer)
    compact = _compact_layer_name(name)
    if name.startswith("WALL") or name == "WAL" or (name.startswith("WAL") and name[3:].isdigit()) or compact.endswith("WALL"):
        return LayerRule(name, "wall", "nonstructural_wall_variant", f"Wall variant layer {name}", material="nonstructural", confidence=0.86)
    if name == "HA" or name.startswith("HAT") or compact.endswith("HAT") or "HATCH" in compact:
        return LayerRule(name, "hatch", "hatch_pattern_variant", f"Hatch variant layer {name}", confidence=0.88)
    if name.startswith("HID"):
        return LayerRule(name, "hidden_line", "hidden_dashed_line_variant", f"Hidden line variant layer {name}", confidence=0.88, linetype="HID")
    if name.startswith("SYM") or compact.endswith("SYM") or "SYMBOL" in compact:
        role = "symbol_text_variant" if any(token in name for token in ("_T", "TEXT", "TXT", "-T")) else "symbol_line_variant"
        return LayerRule(name, "symbol", role, f"Symbol variant layer {name}", confidence=0.88)
    if name.startswith("TXT") or name.startswith("TEXT") or name.startswith("@TEXT") or compact.endswith("TEXT"):
        return LayerRule(name, "annotation", "text_variant", f"Text variant layer {name}", confidence=0.88)
    if name == "CENTER" or (name.startswith("CEN") and name[3:].isdigit()) or compact.endswith("CNTL"):
        return LayerRule(name, "grid_centerline", "centerline_variant", f"Centerline variant layer {name}", confidence=0.86, linetype="CENTER")
    if name.startswith("DIM") or name.endswith("DIM") or "DIM" in compact:
        return LayerRule(name, "annotation", "dimension_variant", f"Dimension variant layer {name}", confidence=0.86)
    if name == "LEADER" or "LEAD" in compact:
        return LayerRule(name, "annotation", "leader_variant", f"Leader variant layer {name}", confidence=0.86)
    if name.startswith("SEC") and name[3:].isdigit():
        return LayerRule(name, "section", "section_line_variant", f"Section variant layer {name}", confidence=0.86)
    if name.startswith("FIN") or "FIN" in compact or "FNSH" in compact:
        return LayerRule(name, "finish", "finish_line_variant", f"Finish variant layer {name}", confidence=0.86)
    if name.startswith("ETC") and (name == "ETC" or name[3:].isdigit()):
        return LayerRule(name, "etc_elevation", "etc_line_variant", f"Other elevation-style variant layer {name}", confidence=0.74)
    return None


def classify_layer(layer: str | None, color: Any = None) -> dict[str, Any]:
    rule = get_layer_rule(layer)
    if rule is None:
        return {
            "layer": str(layer or ""),
            "category": "unknown",
            "role": "unknown",
            "description": "Layer is not defined in the architectural taxonomy.",
            "structural": False,
            "material": None,
            "expected_color_index": None,
            "actual_color": color,
            "color_matches_rule": None,
            "visible": True,
            "confidence": 0.2,
            "notes": "no_layer_rule",
            "linetype": "CONTINUOUS",
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
        "linetype": rule.linetype,
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
