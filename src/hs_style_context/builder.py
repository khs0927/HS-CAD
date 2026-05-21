from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .loader import load_style_sources
from .report import write_style_context_json, write_style_context_md
from .schema import (
    BlockPreference,
    DimensionStylePreference,
    LayerPreference,
    LineStylePreference,
    SheetContext,
    StyleContext,
    TextStylePreference,
)


def _first_pair_value(items: Any) -> Any:
    if isinstance(items, list) and items:
        first = items[0]
        if isinstance(first, (list, tuple)) and first:
            return first[0]
    return None


def _first_numeric_pair_value(items: Any) -> float | None:
    value = _first_pair_value(items)
    try:
        return float(value)
    except Exception:
        return None


def _extract_local_preferences(local: dict[str, Any] | None, context: StyleContext) -> None:
    if not local:
        return

    rec = local.get("recommended_generation_style") or {}
    layer = rec.get("line_layer")
    if layer:
        context.layer_preferences.append(
            LayerPreference(
                role="local_line",
                preferred_layer=str(layer),
                fallback_layer=None,
                confidence=0.9,
                source="local_style_sample",
                reason="recommended_generation_style.line_layer",
            )
        )
        context.layer_preferences.append(
            LayerPreference(
                role="wall",
                preferred_layer=str(layer),
                fallback_layer="WAL1",
                confidence=0.75,
                source="local_style_sample",
                reason="local line layer used as wall/edit context preference",
            )
        )

    context.line_style_preferences.append(
        LineStylePreference(
            role="local_line",
            color=rec.get("line_color"),
            linetype=rec.get("line_linetype"),
            lineweight=rec.get("lineweight"),
            by_layer_ratio=None,
            confidence=0.85 if layer else 0.45,
            source="local_style_sample",
        )
    )

    text_height = rec.get("text_height")
    try:
        text_height = float(text_height) if text_height is not None else None
    except Exception:
        text_height = None

    context.text_style_preferences.append(
        TextStylePreference(
            role="text",
            layer=layer,
            text_style=_first_pair_value(local.get("text_styles")),
            height=text_height or _first_numeric_pair_value(local.get("text_height_families")),
            confidence=0.8 if local.get("text_styles") or text_height else 0.35,
            source="local_style_sample",
        )
    )

    context.dimension_style_preferences.append(
        DimensionStylePreference(
            role="dimension",
            layer=layer,
            dimstyle=rec.get("dimension_style") or _first_pair_value(local.get("dimension_styles")),
            confidence=0.8 if rec.get("dimension_style") or local.get("dimension_styles") else 0.35,
            source="local_style_sample",
        )
    )

    for name, _count in local.get("block_effective_names", [])[:10]:
        context.block_preferences.append(
            BlockPreference(
                role="observed_symbol",
                effective_name=str(name),
                block_name=str(name),
                layer=None,
                confidence=0.65,
                source="local_style_sample",
            )
        )


def _extract_sheet_context(zium: dict[str, Any] | None, context: StyleContext) -> None:
    if not zium:
        return
    definition = zium.get("block_definition") or {}
    scale = None
    scale_dist = zium.get("scale_distribution") or []
    if scale_dist and isinstance(scale_dist[0], (list, tuple)):
        raw = str(scale_dist[0][0])
        try:
            scale = float(raw.split("/")[0])
        except Exception:
            scale = None

    context.sheet_context = SheetContext(
        sheet_block_name=zium.get("block_name") or "ZIUM_sheet_architect",
        insert_layer=zium.get("expected_insert_layer") or _first_pair_value(zium.get("insert_layers")),
        insert_scale=scale,
        representative_usable_area=zium.get("representative_usable_area"),
        title_block_bbox=definition.get("title_block_bbox"),
        needs_visual_check=bool(zium.get("needs_visual_check", True)),
        confidence=0.8 if zium.get("representative_usable_area") else 0.45,
        source="zium_sheet_area",
    )


def _extract_reference_preferences(reference: dict[str, Any] | None, context: StyleContext) -> None:
    if not reference:
        return
    for rule in reference.get("layer_rules", []) or []:
        if not isinstance(rule, dict):
            continue
        context.layer_preferences.append(
            LayerPreference(
                role=str(rule.get("purpose") or rule.get("canonical_layer") or "reference"),
                preferred_layer=rule.get("canonical_layer"),
                fallback_layer=None,
                confidence=float(rule.get("confidence") or 0.5),
                source="reference_style_profile",
                reason=str(rule.get("reasoning") or "reference layer rule"),
            )
        )
    for rule in reference.get("block_rules", []) or []:
        if not isinstance(rule, dict):
            continue
        names = rule.get("block_names") or []
        effective = rule.get("effective_names") or []
        context.block_preferences.append(
            BlockPreference(
                role=str(rule.get("role") or "reference_block"),
                block_name=names[0] if names else None,
                effective_name=effective[0] if effective else None,
                layer=rule.get("preferred_layer"),
                confidence=float(rule.get("confidence") or 0.5),
                source="reference_style_profile",
            )
        )


def build_style_context(
    local_style_sample: dict[str, Any] | None = None,
    zium_sheet_area: dict[str, Any] | None = None,
    active_form_sample: dict[str, Any] | None = None,
    active_scan: dict[str, Any] | None = None,
    reference_style_profile: dict[str, Any] | None = None,
    sources: list[Any] | None = None,
    warnings: list[str] | None = None,
) -> StyleContext:
    context = StyleContext()
    context.sources = list(sources or [])
    context.warnings = list(warnings or [])
    context.metadata = {
        "priority": [
            "user_style",
            "local_style_sample",
            "zium_sheet_area",
            "active_form_sample",
            "active_scan",
            "reference_style_profile",
            "drawing_standards",
            "QA-REVIEW",
        ]
    }

    _extract_local_preferences(local_style_sample, context)
    _extract_sheet_context(zium_sheet_area, context)
    _extract_reference_preferences(reference_style_profile, context)

    if active_form_sample:
        context.warnings.append("active_form_sample loaded; detailed extractor is not implemented in stage23.")
    if active_scan:
        context.warnings.append("active_scan loaded; global counts are reserved for future resolver weighting.")

    if not context.layer_preferences:
        context.layer_preferences.append(
            LayerPreference(
                role="fallback",
                preferred_layer="QA-REVIEW",
                fallback_layer=None,
                confidence=0.2,
                source="fallback",
                reason="no style source loaded",
            )
        )
    return context


def build_style_context_from_paths(
    local_style_sample: str | None = None,
    zium_sheet_area: str | None = None,
    active_form_sample: str | None = None,
    active_scan: str | None = None,
    reference_style_profile: str | None = None,
) -> StyleContext:
    loaded = load_style_sources(
        local_style_sample=local_style_sample,
        zium_sheet_area=zium_sheet_area,
        active_form_sample=active_form_sample,
        active_scan=active_scan,
        reference_style_profile=reference_style_profile,
    )
    return build_style_context(
        local_style_sample=loaded.get("local_style_sample"),
        zium_sheet_area=loaded.get("zium_sheet_area"),
        active_form_sample=loaded.get("active_form_sample"),
        active_scan=loaded.get("active_scan"),
        reference_style_profile=loaded.get("reference_style_profile"),
        sources=loaded.get("_sources", []),
        warnings=loaded.get("_warnings", []),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build HS-CAD style_context.json from optional analysis JSON files.")
    parser.add_argument("--local-style")
    parser.add_argument("--zium-sheet")
    parser.add_argument("--active-form")
    parser.add_argument("--active-scan")
    parser.add_argument("--reference-style")
    parser.add_argument("--out", default="generated/style_context")
    args = parser.parse_args()

    context = build_style_context_from_paths(
        local_style_sample=args.local_style,
        zium_sheet_area=args.zium_sheet,
        active_form_sample=args.active_form,
        active_scan=args.active_scan,
        reference_style_profile=args.reference_style,
    )
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_style_context_json(context, out_dir / "style_context.json")
    write_style_context_md(context, out_dir / "style_context.md")
    print(f"Wrote {out_dir / 'style_context.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
