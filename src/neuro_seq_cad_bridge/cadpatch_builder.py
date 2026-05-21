from __future__ import annotations

from pathlib import Path
from typing import Any

from src.hs_style_context.schema import StyleContext


def _entity_summary(styled_result: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in styled_result.get("entities", []):
        original = item.get("original_entity") or {}
        key = str(original.get("entity_type") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _low_conf_count(styled_result: dict[str, Any]) -> int:
    return sum(1 for item in styled_result.get("entities", []) if item.get("needs_review"))


def _exists(path: str | None) -> bool:
    return bool(path and Path(path).exists())


def _default_base_point(style_context: StyleContext, base_point: list[float] | None) -> list[float]:
    if base_point is not None:
        return base_point
    usable = style_context.sheet_context.representative_usable_area if style_context.sheet_context else None
    if usable and len(usable) >= 2:
        return [float(usable[0]), float(usable[1]), 0.0]
    return [0.0, 0.0, 0.0]


def build_preview_insert_plan(
    styled_result: dict[str, Any],
    centerline_dxf: str | None,
    wallsolid_dxf: str | None,
    style_context: StyleContext,
    base_point: list[float] | None = None,
    scale: float = 1.0,
    rotation: float = 0.0,
    use_wallsolid: bool = True,
) -> dict[str, Any]:
    warnings: list[str] = []
    source_dxf = None

    if use_wallsolid and _exists(wallsolid_dxf):
        source_dxf = str(wallsolid_dxf)
    elif _exists(centerline_dxf):
        source_dxf = str(centerline_dxf)
        if use_wallsolid:
            warnings.append("wallsolid_dxf missing; centerline_dxf used")
    else:
        warnings.append("no source DXF found")

    can_execute = source_dxf is not None
    if not can_execute:
        warnings.append("preview insert cannot execute without a DXF file")

    return {
        "operation": "insert_image_cad_preview",
        "mode": "existing_dwg_preview",
        "dry_run": True,
        "can_execute": can_execute,
        "save": False,
        "undo_mark_required": True,
        "source_dxf": source_dxf,
        "insert_layer": "QA-REVIEW",
        "base_point": _default_base_point(style_context, base_point),
        "scale": scale,
        "rotation": rotation,
        "style_context_used": True,
        "warnings": warnings + list(styled_result.get("warnings") or []) + list(style_context.warnings),
        "entities_summary": _entity_summary(styled_result),
        "low_confidence_count": _low_conf_count(styled_result),
    }
