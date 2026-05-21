from __future__ import annotations

import json
from pathlib import Path

from .schema import StyleContext, to_dict


def write_style_context_json(context: StyleContext, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(to_dict(context), ensure_ascii=False, indent=2), encoding="utf-8")


def write_style_context_md(context: StyleContext, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# HS-CAD Style Context",
        "",
        f"- Version: {context.version}",
        f"- Generated: {context.generated_at}",
        "",
        "## Sources",
    ]
    for source in context.sources:
        lines.append(
            f"- {source.source_type}: path=`{source.path}`, exists={source.exists}, loaded={source.loaded}"
        )
        for warning in source.warnings:
            lines.append(f"  - warning: {warning}")

    lines += ["", "## Resolve Priority"]
    for item in context.metadata.get("priority", []):
        lines.append(f"- {item}")

    lines += ["", "## Layer Preferences"]
    for pref in context.layer_preferences:
        lines.append(
            f"- role={pref.role}, layer={pref.preferred_layer}, fallback={pref.fallback_layer}, "
            f"confidence={pref.confidence}, source={pref.source}, reason={pref.reason}"
        )

    lines += ["", "## Line Style Preferences"]
    for pref in context.line_style_preferences:
        lines.append(
            f"- role={pref.role}, color={pref.color}, linetype={pref.linetype}, "
            f"lineweight={pref.lineweight}, confidence={pref.confidence}, source={pref.source}"
        )

    lines += ["", "## Text Style Preferences"]
    for pref in context.text_style_preferences:
        lines.append(
            f"- role={pref.role}, layer={pref.layer}, style={pref.text_style}, height={pref.height}, "
            f"confidence={pref.confidence}, source={pref.source}"
        )

    lines += ["", "## Dimension Style Preferences"]
    for pref in context.dimension_style_preferences:
        lines.append(
            f"- role={pref.role}, layer={pref.layer}, dimstyle={pref.dimstyle}, "
            f"confidence={pref.confidence}, source={pref.source}"
        )

    lines += ["", "## Sheet Context"]
    if context.sheet_context:
        sheet = context.sheet_context
        lines.extend(
            [
                f"- sheet_block_name: {sheet.sheet_block_name}",
                f"- insert_layer: {sheet.insert_layer}",
                f"- insert_scale: {sheet.insert_scale}",
                f"- representative_usable_area: {sheet.representative_usable_area}",
                f"- title_block_bbox: {sheet.title_block_bbox}",
                f"- needs_visual_check: {sheet.needs_visual_check}",
                f"- confidence: {sheet.confidence}",
                f"- source: {sheet.source}",
            ]
        )
    else:
        lines.append("- none")

    lines += ["", "## Warnings"]
    if context.warnings:
        for warning in context.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")

    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
