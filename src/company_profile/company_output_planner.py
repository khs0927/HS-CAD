"""Plan HS-CAD/ZIUM output from an evidence pack and CompanyDraftingProfile."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CompanyOutputPlan:
    query: str
    titleblock: str | None = None
    recommended_layers: list[dict[str, Any]] = field(default_factory=list)
    recommended_dimension_style: str | None = None
    recommended_text_style: str | None = None
    drafting_notes: list[str] = field(default_factory=list)
    evidence_summary: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _find_profile_value(profile: dict[str, Any], keys: list[str]) -> str | None:
    # Search shallow and nested values for common profile keys.
    for key in keys:
        value = profile.get(key)
        if isinstance(value, str) and value:
            return value

    def walk(obj: Any) -> str | None:
        if isinstance(obj, dict):
            for key in keys:
                value = obj.get(key)
                if isinstance(value, str) and value:
                    return value
            for value in obj.values():
                found = walk(value)
                if found:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = walk(item)
                if found:
                    return found
        return None

    return walk(profile)


def _layer_candidates(profile: dict[str, Any]) -> list[dict[str, Any]]:
    rules = profile.get("layer_rules") or profile.get("layers") or []
    candidates: list[dict[str, Any]] = []
    if isinstance(rules, dict):
        for key, value in rules.items():
            candidates.append({"canonical_element": key, "layer": value, "source": "company_profile"})
    elif isinstance(rules, list):
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            layer = rule.get("preferred_layer") or rule.get("layer") or rule.get("name")
            element = rule.get("canonical_element") or rule.get("element") or rule.get("role") or "UNKNOWN"
            if layer:
                candidates.append({"canonical_element": element, "layer": layer, "source": rule.get("source") or "company_profile"})
    return candidates


def build_company_output_plan(
    evidence_path: str | Path,
    company_profile_path: str | Path,
    out_dir: str | Path,
) -> CompanyOutputPlan:
    evidence = _load_json(evidence_path)
    profile = _load_json(company_profile_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    plan = CompanyOutputPlan(query=evidence.get("query") or "")
    plan.titleblock = _find_profile_value(profile, ["preferred_titleblock_name", "titleblock_name", "preferred_titleblock"])
    plan.recommended_dimension_style = _find_profile_value(profile, ["preferred_dimension_style", "dimension_style", "dimstyle"])
    plan.recommended_text_style = _find_profile_value(profile, ["preferred_text_style", "text_style", "font_style"])
    plan.recommended_layers = _layer_candidates(profile)

    # Evidence summary
    grouped = evidence.get("grouped") or {}
    for table, hits in grouped.items():
        if not isinstance(hits, list):
            continue
        for hit in hits[:3]:
            text = (hit.get("text") or "").replace("\n", " ")
            if text:
                plan.evidence_summary.append(f"[{table}] {text[:240]}")

    if not plan.titleblock:
        plan.warnings.append("Company profile did not provide a preferred titleblock. Use active drawing sampling or QA-REVIEW.")
    if not plan.recommended_dimension_style:
        plan.warnings.append("Company profile did not provide a dimension style. Use active drawing sampling or fallback.")
    if not plan.recommended_layers:
        plan.warnings.append("No company layer mapping found. Use current drawing local style sampling first.")

    plan.drafting_notes.extend(
        [
            "외부 도면의 레이어/도곽/문자 스타일은 출력 기준으로 사용하지 않는다.",
            "검색된 재료·규격·상세 구성만 일반 건축 지식으로 활용한다.",
            "실제 작성 시 현재 활성 도면 주변 속성 샘플링을 1순위로 적용한다.",
            "CompanyDraftingProfile은 2순위 출력 기준으로 사용한다.",
            "저신뢰 요소는 QA-REVIEW 또는 검수 레이어에 분리한다.",
        ]
    )

    data = asdict(plan)
    (out / "company_output_plan.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "company_output_plan.md").write_text(render_company_output_plan_markdown(plan), encoding="utf-8")
    return plan


def render_company_output_plan_markdown(plan: CompanyOutputPlan) -> str:
    lines = ["# Company Output Plan", ""]
    lines.append(f"## Query")
    lines.append("")
    lines.append(plan.query or "-")
    lines.append("")
    lines.append("## Company Drafting Defaults")
    lines.append("")
    lines.append(f"- Titleblock: `{plan.titleblock or 'unresolved'}`")
    lines.append(f"- Dimension style: `{plan.recommended_dimension_style or 'unresolved'}`")
    lines.append(f"- Text style: `{plan.recommended_text_style or 'unresolved'}`")
    lines.append("")
    lines.append("## Recommended Layers")
    lines.append("")
    if plan.recommended_layers:
        for item in plan.recommended_layers[:50]:
            lines.append(f"- {item.get('canonical_element', 'UNKNOWN')} → `{item.get('layer')}` ({item.get('source', '-')})")
    else:
        lines.append("- No layer recommendations.")
    lines.append("")
    lines.append("## Evidence Summary")
    lines.append("")
    for item in plan.evidence_summary[:20]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Drafting Notes")
    lines.append("")
    for note in plan.drafting_notes:
        lines.append(f"- {note}")
    if plan.warnings:
        lines.append("")
        lines.append("## Warnings")
        for warning in plan.warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines).rstrip() + "\n"
