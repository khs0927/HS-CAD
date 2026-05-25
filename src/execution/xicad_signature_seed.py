from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class XiCADSignatureSeed:
    alias: str
    source: str
    status: str
    requires_human_review: bool
    evidence: dict[str, Any]
    signature_hint: dict[str, Any]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_signature_seeds_from_rules(rules: dict[str, Any], *, source: str = "xicad_rules") -> list[XiCADSignatureSeed]:
    seeds: list[XiCADSignatureSeed] = []
    wall_styles = rules.get("wall_styles") or {}
    if wall_styles:
        seeds.append(_wall_seed(wall_styles, source=source))

    configs = rules.get("config_variables") or {}
    door_configs = {key: value for key, value in configs.items() if "door" in key.lower()}
    if door_configs:
        seeds.append(_opening_seed("D1", door_configs, source=source, family="door"))

    window_configs = {key: value for key, value in configs.items() if "win" in key.lower()}
    if window_configs:
        seeds.append(_opening_seed("W1", window_configs, source=source, family="window"))

    block_rules = rules.get("block_layer_rules") or {}
    column_rules = {
        key: value
        for key, value in block_rules.items()
        if "col" in key.lower() or "column" in key.lower() or "기둥" in str(value)
    }
    if column_rules:
        seeds.append(_column_seed(column_rules, source=source))

    return seeds


def _wall_seed(wall_styles: dict[str, Any], *, source: str) -> XiCADSignatureSeed:
    thicknesses = sorted(
        {
            float(style.get("total_thickness"))
            for style in wall_styles.values()
            if isinstance(style, dict) and isinstance(style.get("total_thickness"), (int, float))
        }
    )
    layer_counts: dict[str, int] = {}
    for style in wall_styles.values():
        if not isinstance(style, dict):
            continue
        for line in style.get("lines", []) or []:
            layer = str(line.get("layer") or "")
            if layer:
                layer_counts[layer] = layer_counts.get(layer, 0) + 1

    return XiCADSignatureSeed(
        alias="WAL",
        source=source,
        status="seed_from_xicad_text_rules",
        requires_human_review=True,
        evidence={
            "wall_style_count": len(wall_styles),
            "observed_thicknesses": thicknesses[:50],
            "layer_counts": dict(sorted(layer_counts.items())),
        },
        signature_hint={
            "geometry_patterns": [{"kind": "parallel_line_pair", "min_count": 1}],
            "expected_added_types": ["LINE", "LWPOLYLINE"],
            "expected_layer_names": sorted(layer_counts)[:50],
            "thickness_candidates": thicknesses[:50],
        },
        warnings=["Seed only; verify with entity delta from approved copy before config promotion."],
    )


def _opening_seed(alias: str, configs: dict[str, Any], *, source: str, family: str) -> XiCADSignatureSeed:
    widths: list[float] = []
    for cfg in configs.values():
        if isinstance(cfg, dict) and isinstance(cfg.get("default_width"), (int, float)):
            widths.append(float(cfg["default_width"]))

    return XiCADSignatureSeed(
        alias=alias,
        source=source,
        status="seed_from_xicad_text_rules",
        requires_human_review=True,
        evidence={
            "family": family,
            "config_keys": sorted(configs),
            "default_widths": sorted(set(widths)),
        },
        signature_hint={
            "geometry_patterns": [
                {"kind": "opening_gap", "min_count": 1},
                {"kind": "block_or_arc_insert", "min_count": 1},
            ],
            "width_candidates": sorted(set(widths)),
        },
        warnings=["Seed only; opening trim behavior must be verified by snapshot delta."],
    )


def _column_seed(column_rules: dict[str, Any], *, source: str) -> XiCADSignatureSeed:
    layers = sorted({str(value.get("layer")) for value in column_rules.values() if isinstance(value, dict) and value.get("layer")})
    return XiCADSignatureSeed(
        alias="COL",
        source=source,
        status="seed_from_xicad_text_rules",
        requires_human_review=True,
        evidence={
            "rule_count": len(column_rules),
            "layers": layers,
        },
        signature_hint={
            "geometry_patterns": [{"kind": "closed_rect_or_block_insert", "min_count": 1}],
            "expected_layer_names": layers,
        },
        warnings=["Seed only; structural column geometry must be verified by snapshot delta."],
    )
