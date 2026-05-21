from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .company_drafting_profile import CompanyDraftingProfile


@dataclass(slots=True)
class CompanyOutputRecommendation:
    situation_tag: str
    canonical_elements: list[str] = field(default_factory=list)
    recommended_company_layers: list[dict[str, Any]] = field(default_factory=list)
    recommended_dimension_style: str | None = None
    recommended_titleblock: str | None = None
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def map_canonical_to_company(
    *,
    situation_tag: str,
    canonical_elements: list[str],
    profile: CompanyDraftingProfile,
) -> CompanyOutputRecommendation:
    rec = CompanyOutputRecommendation(situation_tag=situation_tag, canonical_elements=canonical_elements)

    mapping = {m.get("canonical_element"): m.get("candidate_layers", []) for m in profile.canonical_output_mapping}
    for element in canonical_elements:
        candidates = mapping.get(element, [])
        if candidates:
            rec.recommended_company_layers.append({"canonical_element": element, "layer": candidates[0], "source": "CompanyDraftingProfile"})
        else:
            rec.recommended_company_layers.append({"canonical_element": element, "layer": "QA-REVIEW", "source": "fallback"})

    if profile.dimension_rules:
        rec.recommended_dimension_style = next(iter(profile.dimension_rules.keys()))
    if profile.titleblock_rules:
        rec.recommended_titleblock = next(iter(profile.titleblock_rules.keys()))

    rec.notes.append("외부 corpus의 건축 지식을 HS-CAD 내부 CompanyDraftingProfile 기준으로 변환한 추천입니다.")
    return rec
