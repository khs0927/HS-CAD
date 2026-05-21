from __future__ import annotations

from .schema import StyleContext, StyleResolveRequest, StyleResolveResult


DEFAULT_LAYER_BY_TYPE = {
    "wall": "WAL1",
    "masonry_wall": "WAL2",
    "column": "COL",
    "door": "DOOR",
    "window": "WIN",
    "window_frame": "WINBAR",
    "hatch": "HAT",
    "text": "TEXT",
    "dimension": "DIM",
    "leader": "DIMLE",
    "raw_line": "RAW_LINES",
    "low_confidence": "AI_LOWCONF",
}


def _find_layer_pref(context: StyleContext, roles: list[str]) -> tuple[str | None, float, str, str]:
    for role in roles:
        prefs = [pref for pref in context.layer_preferences if pref.role == role and pref.preferred_layer]
        if prefs:
            pref = sorted(prefs, key=lambda x: x.confidence, reverse=True)[0]
            return pref.preferred_layer, pref.confidence, pref.reason, pref.source
    return None, 0.0, "", ""


def _first_line_style(context: StyleContext):
    if not context.line_style_preferences:
        return None
    return sorted(context.line_style_preferences, key=lambda x: x.confidence, reverse=True)[0]


def _first_text_style(context: StyleContext):
    if not context.text_style_preferences:
        return None
    return sorted(context.text_style_preferences, key=lambda x: x.confidence, reverse=True)[0]


def _first_dim_style(context: StyleContext):
    if not context.dimension_style_preferences:
        return None
    return sorted(context.dimension_style_preferences, key=lambda x: x.confidence, reverse=True)[0]


def resolve_style(request: StyleResolveRequest, context: StyleContext) -> StyleResolveResult:
    element_type = (request.element_type or "unknown").lower()
    mode = request.mode or "existing_dwg_preview"
    confidence = request.confidence if request.confidence is not None else 0.7

    if request.user_layer:
        layer = request.user_layer
        reason = "user_layer explicitly provided"
        source = "user"
        layer_conf = 1.0
    elif element_type == "raw_line" and mode == "existing_dwg_preview":
        layer, layer_conf, reason, source = "QA-REVIEW", 0.9, "raw line isolated for existing DWG preview", "policy"
    elif element_type == "low_confidence":
        layer, layer_conf, reason, source = "AI_LOWCONF", 0.9, "low confidence entity preserved", "policy"
    else:
        roles = [element_type, request.role or "", "local_line", "fallback"]
        layer, layer_conf, reason, source = _find_layer_pref(context, roles)
        if not layer:
            layer = DEFAULT_LAYER_BY_TYPE.get(element_type, "QA-REVIEW")
            layer_conf = 0.45
            reason = "default layer fallback"
            source = "default"

    line_style = _first_line_style(context)
    text_style = _first_text_style(context)
    dim_style = _first_dim_style(context)

    needs_review = confidence < 0.65 or layer_conf < 0.5 or layer in {"AI_LOWCONF", "QA-REVIEW"}
    result_conf = min(max(confidence, 0.0), 1.0) * 0.6 + min(max(layer_conf, 0.0), 1.0) * 0.4

    return StyleResolveResult(
        element_type=element_type,
        target_layer=layer,
        color=line_style.color if line_style else None,
        linetype=line_style.linetype if line_style else None,
        lineweight=line_style.lineweight if line_style else None,
        text_style=text_style.text_style if text_style else None,
        text_height=text_style.height if text_style else None,
        dimstyle=dim_style.dimstyle if dim_style else None,
        block_name=None,
        needs_review=needs_review,
        confidence=round(result_conf, 4),
        reason=reason,
        source=source,
    )
