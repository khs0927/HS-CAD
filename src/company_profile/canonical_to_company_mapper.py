from __future__ import annotations

from typing import Any


CANONICAL_FALLBACK = {
    "WALL": "WAL1",
    "COLUMN": "COL",
    "BEAM": "COL",
    "STRUCTURAL_STEEL": "COL",
    "CENTERLINE": "중심선",
    "GRID": "중심선",
    "DIMENSION": "치수",
    "MATERIAL_NOTE": "TEXT",
    "FINISH_NOTE": "TEXT",
    "DOOR": "DOOR",
    "WINDOW": "WIN",
    "PANEL_SYSTEM": "WAL1",
    "CEILING_SYSTEM": "TEXT",
    "FIRE_SAFETY": "TEXT",
    "ACOUSTIC": "TEXT",
}


def build_company_recommendations(query_result: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Canonical Knowledge를 HS-CAD 회사 문법 기반 출력 추천으로 변환한다.

    외부 도면 레이어명은 사용하지 않고, profile에서 추출한 회사 기준을 우선한다.
    """
    canonical_elements = _extract_elements(query_result)
    situations = [r.get("tag") for r in query_result.get("related_situations", []) if r.get("tag")]
    materials = [r.get("normalized_name") or r.get("name") for r in query_result.get("related_materials", []) if r.get("normalized_name") or r.get("name")]
    specs = [r.get("raw_text") or r.get("normalized_value") for r in query_result.get("related_specifications", []) if r.get("raw_text") or r.get("normalized_value")]

    layer_rules = _profile_layer_rules(profile)
    dim_rule = _profile_dimension_rule(profile)
    title_rule = _profile_titleblock_rule(profile)
    text_rule = _profile_text_rule(profile)

    recs: list[dict[str, Any]] = []
    if situations:
        recs.append(
            {
                "type": "situation_summary",
                "summary": f"관련 상황 `{', '.join(situations[:5])}`은 회사 도면 기준으로 상세/주석/치수 세트를 함께 검토하세요.",
                "situations": situations[:10],
                "confidence": 0.78,
            }
        )

    for element in canonical_elements:
        layer = layer_rules.get(element) or CANONICAL_FALLBACK.get(element) or "QA-REVIEW"
        recs.append(
            {
                "type": "layer_mapping",
                "canonical_element": element,
                "recommended_layer": layer,
                "summary": f"{element} 요소는 회사 profile 기준 `{layer}` 레이어 후보로 출력하세요.",
                "source": "company_profile" if element in layer_rules else "fallback_candidate",
                "confidence": 0.82 if element in layer_rules else 0.55,
            }
        )

    if dim_rule:
        recs.append(
            {
                "type": "dimension_style",
                "recommended_dimension_layer": dim_rule.get("preferred_dimension_layer") or dim_rule.get("layer") or "치수",
                "recommended_dimension_style": dim_rule.get("preferred_dimension_style") or dim_rule.get("style") or "300DIM",
                "summary": "치수는 회사 profile에서 추출한 치수 레이어/스타일을 우선 적용하세요.",
                "confidence": dim_rule.get("confidence", 0.75),
            }
        )

    if title_rule:
        recs.append(
            {
                "type": "titleblock",
                "recommended_titleblock": title_rule.get("preferred_titleblock_name") or title_rule.get("name") or "ZIUM_sheet_architect",
                "summary": "상세/시트 출력 시 회사 profile에서 추출한 도곽 블록을 재사용하세요.",
                "confidence": title_rule.get("confidence", 0.75),
            }
        )

    if text_rule:
        recs.append(
            {
                "type": "text_style",
                "recommended_text_style": text_rule.get("preferred_text_style") or text_rule.get("style"),
                "summary": "재료/성능/상세 주석은 회사 profile의 문자 스타일과 축척별 높이 정책을 따르세요.",
                "confidence": text_rule.get("confidence", 0.7),
            }
        )

    if materials or specs:
        recs.append(
            {
                "type": "note_content",
                "materials": materials[:10],
                "specifications": specs[:10],
                "summary": f"주석에는 재료 `{', '.join(materials[:5])}` 및 규격 `{', '.join(specs[:5])}` 근거를 반영하세요.",
                "confidence": 0.72,
            }
        )

    return recs


def _extract_elements(query_result: dict[str, Any]) -> list[str]:
    elements = []
    for pattern in query_result.get("related_detail_patterns", []) or []:
        raw = pattern.get("elements_json")
        if isinstance(raw, str):
            try:
                import json
                elements.extend(json.loads(raw))
            except Exception:
                pass
        elif isinstance(raw, list):
            elements.extend(raw)

    # 쿼리 결과에 직접 canonical elements가 없을 때 상황/재료 기반으로 보강
    text = " ".join(str(v) for v in query_result.values())
    if "H빔" in text or "h_beam" in text or "steel" in text:
        elements.append("STRUCTURAL_STEEL")
    if "판넬" in text or "panel" in text:
        elements.append("PANEL_SYSTEM")
    if "창" in text or "window" in text or "방음시창" in text:
        elements.append("WINDOW")
    if "문" in text or "door" in text or "방음문" in text:
        elements.append("DOOR")
    if "치수" in text or "dimension" in text:
        elements.append("DIMENSION")

    # 순서 보존 중복 제거
    seen = set()
    result = []
    for e in elements:
        if e and e not in seen:
            seen.add(e)
            result.append(e)
    return result or ["MATERIAL_NOTE", "DIMENSION"]


def _profile_layer_rules(profile: dict[str, Any]) -> dict[str, str]:
    rules: dict[str, str] = {}
    for item in profile.get("layer_rules", []) or []:
        if not isinstance(item, dict):
            continue
        canonical = item.get("canonical_element") or item.get("element")
        layer = item.get("preferred_layer") or item.get("layer")
        if canonical and layer:
            rules[str(canonical)] = str(layer)
    for item in profile.get("canonical_output_mapping", []) or []:
        if not isinstance(item, dict):
            continue
        canonical = item.get("canonical_element")
        layer = item.get("layer") or item.get("preferred_layer")
        if canonical and layer:
            rules[str(canonical)] = str(layer)
    return rules


def _profile_dimension_rule(profile: dict[str, Any]) -> dict[str, Any]:
    rules = profile.get("dimension_rules") or {}
    if isinstance(rules, list):
        return rules[0] if rules else {}
    return rules if isinstance(rules, dict) else {}


def _profile_titleblock_rule(profile: dict[str, Any]) -> dict[str, Any]:
    rules = profile.get("titleblock_rules") or {}
    if isinstance(rules, list):
        return rules[0] if rules else {}
    return rules if isinstance(rules, dict) else {}


def _profile_text_rule(profile: dict[str, Any]) -> dict[str, Any]:
    rules = profile.get("text_style_rules") or {}
    if isinstance(rules, list):
        return rules[0] if rules else {}
    return rules if isinstance(rules, dict) else {}


from dataclasses import dataclass
from typing import Any

@dataclass(slots=True)
class CompanyMappingResult:
    recommended_company_layers: list[dict[str, Any]]
    recommended_dimension_style: str | None = None


def map_canonical_to_company(*, situation_tag: str, canonical_elements: list[str], profile: Any) -> CompanyMappingResult:
    """Compatibility wrapper expected by tests.

    Generates a minimal mapping result based on the provided profile and
    canonical elements. ``situation_tag`` is accepted for signature compatibility
    but not used in this simplified implementation.
    """
    # Convert possible Pydantic model to plain dict
    profile_dict = profile.dict() if hasattr(profile, "dict") else dict(profile)

    # Resolve layer rules and fallbacks
    layer_rules = _profile_layer_rules(profile_dict)
    recommended_layers: list[dict[str, Any]] = []
    for elem in canonical_elements:
        layer = layer_rules.get(elem) or CANONICAL_FALLBACK.get(elem) or "QA-REVIEW"
        recommended_layers.append({"canonical_element": elem, "layer": layer})

    # Resolve dimension style – choose the first key if no explicit style
    dim_rule = _profile_dimension_rule(profile_dict)
    recommended_dim_style: str | None = None
    if dim_rule:
        # Preferred style keys
        preferred = dim_rule.get("preferred_dimension_style") or dim_rule.get("style")
        if preferred:
            recommended_dim_style = preferred
        else:
            # Fallback to first key of the dict
            if isinstance(dim_rule, dict):
                recommended_dim_style = next(iter(dim_rule))
    return CompanyMappingResult(
        recommended_company_layers=recommended_layers,
        recommended_dimension_style=recommended_dim_style,
    )