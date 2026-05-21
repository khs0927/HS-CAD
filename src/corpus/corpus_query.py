from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .knowledge_store import KnowledgeStore

try:
    from src.company_profile.canonical_to_company_mapper import build_company_recommendations
except Exception:  # noqa: BLE001
    build_company_recommendations = None  # type: ignore


def query_kb(
    kb_path: str | Path,
    query: str,
    company_profile_path: str | Path | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    store = KnowledgeStore(kb_path)
    # Tokenize query and aggregate results for each token to enable partial matches.
    tokens = [t for t in query.split() if t]
    aggregated: dict[str, list[dict[str, Any]]] = {
        "situations": [],
        "materials": [],
        "specifications": [],
        "patterns": [],
        "lessons": [],
        "texts": [],
    }
    for token in tokens:
        raw = store.search(token, limit=limit)
        aggregated["situations"].extend(raw.get("situations", []))
        aggregated["materials"].extend(raw.get("materials", []))
        aggregated["specifications"].extend(raw.get("specifications", []))
        aggregated["patterns"].extend(raw.get("patterns", []))
        aggregated["lessons"].extend(raw.get("lessons", []))
        aggregated["texts"].extend(raw.get("texts", []))
    # Deduplicate entries based on primary key 'id' if present.
    def dedup(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple] = set()
        out: list[dict[str, Any]] = []
        for it in items:
            key = tuple(it.get(k) for k in ("id", "file_id"))
            if key and key in seen:
                continue
            seen.add(key)
            out.append(it)
        return out
    related_situations = dedup(aggregated["situations"])
    related_materials = dedup(aggregated["materials"])
    related_specifications = dedup(aggregated["specifications"])
    related_patterns = dedup(aggregated["patterns"])
    architectural_lessons = dedup(aggregated["lessons"])
    evidence_texts = dedup(aggregated["texts"])

    result: dict[str, Any] = {
        "query": query,
        "related_situations": related_situations,
        "related_materials": related_materials,
        "related_specifications": related_specifications,
        "related_detail_patterns": related_patterns,
        "architectural_lessons": architectural_lessons,
        "evidence_texts": evidence_texts,
        "company_output_recommendations": [],
        "confidence": _estimate_confidence({
            "situations": related_situations,
            "materials": related_materials,
            "specifications": related_specifications,
            "patterns": related_patterns,
            "lessons": architectural_lessons,
            "texts": evidence_texts,
        }),
        "warnings": [],
    }

    if company_profile_path and build_company_recommendations:
        try:
            profile = json.loads(Path(company_profile_path).read_text(encoding="utf-8"))
            result["company_output_recommendations"] = build_company_recommendations(result, profile)
        except Exception as exc:  # noqa: BLE001
            result["warnings"].append(f"company profile mapping failed: {exc}")
    elif company_profile_path:
        result["warnings"].append("canonical_to_company_mapper is unavailable")

    store.close()
    return result


def format_query_result_markdown(result: dict[str, Any]) -> str:
    lines = [f"# Corpus Query Result", "", f"**Query:** {result.get('query', '')}", ""]

    def section(title: str, rows: list[dict[str, Any]], key: str):
        lines.extend([f"## {title}", ""])
        if not rows:
            lines.append("- 결과 없음")
            lines.append("")
            return
        for row in rows[:10]:
            value = row.get(key) or row.get("normalized_name") or row.get("raw_text") or row.get("lesson") or row.get("text")
            ctx = row.get("context") or row.get("evidence") or ""
            lines.append(f"- **{value}**")
            if ctx:
                lines.append(f"  - 근거: {ctx}")
        lines.append("")

    section("관련 상황", result.get("related_situations", []), "tag")
    section("관련 재료", result.get("related_materials", []), "normalized_name")
    section("관련 규격/성능", result.get("related_specifications", []), "raw_text")
    section("상세 패턴", result.get("related_detail_patterns", []), "pattern_name")
    section("건축 lesson", result.get("architectural_lessons", []), "lesson")

    recs = result.get("company_output_recommendations") or []
    lines.extend(["## 회사 기준 출력 추천", ""])
    if not recs:
        lines.append("- 추천 없음")
    else:
        for rec in recs[:10]:
            lines.append(f"- {rec.get('summary', rec)}")
    lines.append("")
    return "\n".join(lines)


def _estimate_confidence(raw: dict[str, list[dict[str, Any]]]) -> float:
    hit_count = sum(len(v) for v in raw.values())
    return min(0.95, 0.25 + hit_count * 0.04)
