from __future__ import annotations

from pathlib import Path
from typing import Any

from .knowledge_store import KnowledgeStore


def build_report(kb_path: str | Path, out_path: str | Path, company_profile_path: str | Path | None = None) -> str:
    store = KnowledgeStore(kb_path)
    counts = store.table_counts()

    lines: list[str] = []
    lines.append("# Architectural Drawing Knowledge Corpus Report")
    lines.append("")
    lines.append("## 1. 처리 현황")
    lines.append("")
    for key, value in counts.items():
        lines.append(f"- {key}: {value}")
    lines.append("")

    _top_section(lines, "## 2. 자주 등장하는 재료", store.top_values("materials", "normalized_name", 20))
    _top_section(lines, "## 3. 자주 등장하는 재료 카테고리", store.top_values("materials", "category", 20))
    _top_section(lines, "## 4. 자주 등장하는 규격/성능 유형", store.top_values("specifications", "spec_type", 20))
    _top_section(lines, "## 5. 자주 등장하는 치수 역할", store.top_values("dimensions", "role", 20))
    _top_section(lines, "## 6. 상황별 도면 구성 태그", store.top_values("situations", "tag", 20))
    _top_section(lines, "## 7. Canonical 건축 요소", store.top_values("canonical_elements", "canonical_element", 20))

    lines.append("## 8. 건축설계 Lesson")
    lines.append("")
    lessons = store.conn.execute(
        "SELECT situation_tag, lesson, evidence_count, confidence FROM architectural_lessons ORDER BY evidence_count DESC, confidence DESC LIMIT 30"
    ).fetchall()
    if not lessons:
        lines.append("- 아직 생성된 lesson이 없습니다. `corpus-learn`을 실행하세요.")
    else:
        for row in lessons:
            lines.append(f"- **{row['situation_tag']}**: {row['lesson']} (근거 {row['evidence_count']}건, confidence {row['confidence']:.2f})")
    lines.append("")

    lines.append("## 9. CompanyDraftingProfile 기반 출력 추천")
    lines.append("")
    if company_profile_path:
        lines.append(f"- 사용된 company profile: `{company_profile_path}`")
        lines.append("- 외부 도면의 레이어/도곽/문자 스타일은 직접 적용하지 않고, HS-CAD 내부 회사 기준으로 매핑해야 합니다.")
    else:
        lines.append("- company profile이 지정되지 않았습니다. `company-profile-build` 후 다시 실행하세요.")
    lines.append("")

    lines.append("## 10. 오류/주의")
    lines.append("")
    errors = store.conn.execute("SELECT file_id, stage, error_message FROM processing_errors ORDER BY id DESC LIMIT 30").fetchall()
    if not errors:
        lines.append("- 기록된 처리 오류 없음")
    else:
        for row in errors:
            lines.append(f"- `{row['file_id']}` / {row['stage']}: {row['error_message']}")
    lines.append("")

    text = "\n".join(lines)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    store.close()
    return text


def _top_section(lines: list[str], title: str, rows: list[dict[str, Any]]) -> None:
    lines.append(title)
    lines.append("")
    if not rows:
        lines.append("- 결과 없음")
    else:
        for row in rows:
            lines.append(f"- {row['value']}: {row['count']}회")
    lines.append("")
