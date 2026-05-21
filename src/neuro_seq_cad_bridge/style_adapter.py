from __future__ import annotations

from typing import Any

from src.hs_style_context.resolver import resolve_style
from src.hs_style_context.schema import StyleContext, StyleResolveRequest, to_dict

from .result_loader import iter_neuro_entities, normalize_neuro_entity


def apply_style_context_to_neuro_result(
    neuro_result: dict[str, Any],
    style_context: StyleContext,
    mode: str = "existing_dwg_preview",
) -> dict[str, Any]:
    styled_entities: list[dict[str, Any]] = []
    warnings = list(neuro_result.get("warnings") or [])

    for raw in iter_neuro_entities(neuro_result):
        entity = normalize_neuro_entity(raw)
        resolve = resolve_style(
            StyleResolveRequest(
                element_type=entity["entity_type"],
                role=entity["entity_type"],
                nearby_handle=None,
                user_layer=None,
                user_style=None,
                confidence=entity["confidence"],
                mode=mode,
            ),
            style_context,
        )
        styled_entities.append(
            {
                "original_entity": entity,
                "target_layer": resolve.target_layer,
                "color": resolve.color,
                "linetype": resolve.linetype,
                "lineweight": resolve.lineweight,
                "text_style": resolve.text_style,
                "text_height": resolve.text_height,
                "dimstyle": resolve.dimstyle,
                "block_name": resolve.block_name,
                "needs_review": resolve.needs_review,
                "style_confidence": resolve.confidence,
                "style_reason": resolve.reason,
                "style_source": resolve.source,
            }
        )

    return {
        "version": "stage23-styled-neuro-result-v1",
        "mode": mode,
        "source_result_metadata": neuro_result.get("metadata", {}),
        "style_context_summary": {
            "version": style_context.version,
            "warnings": style_context.warnings,
        },
        "entities": styled_entities,
        "warnings": warnings,
        "style_context": to_dict(style_context),
    }
