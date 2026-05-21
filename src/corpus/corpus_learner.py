from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .knowledge_store import KnowledgeStore


def learn_from_kb(kb_path: str | Path, out_dir: str | Path | None = None, top_n: int = 20) -> dict[str, Any]:
    store = KnowledgeStore(kb_path)

    summary: dict[str, Any] = {
        "counts": store.table_counts(),
        "top_materials": store.top_values("materials", "normalized_name", top_n),
        "top_material_categories": store.top_values("materials", "category", top_n),
        "top_spec_types": store.top_values("specifications", "spec_type", top_n),
        "top_dimension_roles": store.top_values("dimensions", "role", top_n),
        "top_situations": store.top_values("situations", "tag", top_n),
        "top_elements": store.top_values("canonical_elements", "canonical_element", top_n),
        "lessons": [],
    }

    # 기존 lesson을 지우지 않고 누적하면 중복이 생기므로 MVP에서는 새로 계산한 lesson도 summary에 넣고,
    # 같은 문구가 없다면 architectural_lessons에도 추가한다.
    lessons = _build_lessons(store)
    for lesson in lessons:
        summary["lessons"].append(lesson)
        if not _lesson_exists(store, lesson["situation_tag"], lesson["lesson"]):
            store.add_lesson(
                lesson["situation_tag"],
                lesson["lesson"],
                lesson["evidence_count"],
                lesson["confidence"],
            )

    summary["counts_after_learning"] = store.table_counts()
    store.close()

    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "learning_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return summary


def _build_lessons(store: KnowledgeStore) -> list[dict[str, Any]]:
    conn = store.conn
    situations = [
        dict(r)
        for r in conn.execute(
            "SELECT tag, COUNT(DISTINCT file_id) AS file_count FROM situations WHERE tag != 'unknown' GROUP BY tag ORDER BY file_count DESC"
        ).fetchall()
    ]
    lessons: list[dict[str, Any]] = []
    for s in situations:
        tag = s["tag"]
        file_count = int(s["file_count"])
        mats = [
            r["normalized_name"]
            for r in conn.execute(
                """
                SELECT m.normalized_name, COUNT(*) AS c
                FROM materials m
                JOIN situations s ON s.file_id = m.file_id
                WHERE s.tag = ? AND m.normalized_name != ''
                GROUP BY m.normalized_name
                ORDER BY c DESC
                LIMIT 6
                """,
                (tag,),
            ).fetchall()
        ]
        specs = [
            r["spec_type"] + ":" + r["normalized_value"]
            for r in conn.execute(
                """
                SELECT sp.spec_type, sp.normalized_value, COUNT(*) AS c
                FROM specifications sp
                JOIN situations s ON s.file_id = sp.file_id
                WHERE s.tag = ? AND sp.normalized_value != ''
                GROUP BY sp.spec_type, sp.normalized_value
                ORDER BY c DESC
                LIMIT 5
                """,
                (tag,),
            ).fetchall()
        ]
        elems = [
            r["canonical_element"]
            for r in conn.execute(
                """
                SELECT e.canonical_element, COUNT(*) AS c
                FROM canonical_elements e
                JOIN situations s ON s.file_id = e.file_id
                WHERE s.tag = ? AND e.canonical_element != 'UNKNOWN'
                GROUP BY e.canonical_element
                ORDER BY c DESC
                LIMIT 5
                """,
                (tag,),
            ).fetchall()
        ]

        parts = []
        if mats:
            parts.append(f"주요 재료는 {', '.join(mats)}")
        if specs:
            parts.append(f"자주 보이는 규격/성능은 {', '.join(specs)}")
        if elems:
            parts.append(f"관련 도면 요소는 {', '.join(elems)}")

        lesson_text = f"{tag} 관련 도면에서는 " + "; ".join(parts) + "이 함께 검토되는 경향이 있다."
        if not parts:
            lesson_text = f"{tag} 관련 도면에서는 관련 주석, 치수, 재료 표기를 함께 확인해야 한다."

        lessons.append(
            {
                "situation_tag": tag,
                "lesson": lesson_text,
                "evidence_count": file_count,
                "confidence": min(0.92, 0.55 + file_count * 0.05),
            }
        )
    return lessons


def _lesson_exists(store: KnowledgeStore, tag: str, lesson: str) -> bool:
    row = store.conn.execute(
        "SELECT 1 FROM architectural_lessons WHERE situation_tag = ? AND lesson = ? LIMIT 1",
        (tag, lesson),
    ).fetchone()
    return row is not None
