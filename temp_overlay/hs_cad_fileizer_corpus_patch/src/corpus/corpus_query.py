from __future__ import annotations

from pathlib import Path
from typing import Any

from .knowledge_store import KnowledgeStore


def query_corpus(db_path: Path, query: str, *, limit: int = 20) -> dict[str, Any]:
    """Simple corpus query.

    This is intentionally deterministic. A later agent can replace keyword
    splitting with a richer Korean tokenizer or FTS5 ranking.
    """
    store = KnowledgeStore(Path(db_path))
    results = store.query_keyword(query, limit=limit)
    return {
        "query": query,
        "related_materials": results["materials"],
        "related_specifications": results["specifications"],
        "related_situations": results["situations"],
        "architectural_lessons": _lessons_from_results(results),
        "warnings": [],
    }


def _lessons_from_results(results: dict[str, list[dict[str, Any]]]) -> list[str]:
    tags = {r.get("tag") for r in results.get("situations", []) if r.get("tag")}
    lessons: list[str] = []
    if "방음시창" in tags:
        lessons.append("방음시창 상세에서는 창호 크기, 프레임, 유리 사양, 코킹/실링, 차음성능 표기를 함께 확인한다.")
    if "H빔접합" in tags or "판넬마감" in tags:
        lessons.append("판넬-H빔 접합부는 판넬 두께, 하지철물, 후레싱, 실란트, 피스 고정, 돌출 간격을 함께 검토한다.")
    if "천장마감" in tags:
        lessons.append("천장 마감은 경량철골 천장틀, 석고텍스, 보 하부 높이, 마감 여유 공간, 최종 천장고를 함께 검토한다.")
    return lessons
