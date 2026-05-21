from __future__ import annotations

from pathlib import Path
from typing import Any

from .corpus_learner import learn_from_corpus


def build_corpus_report(db_path: Path, out_path: Path) -> Path:
    summary = learn_from_corpus(db_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# Architectural Drawing Knowledge Corpus Report",
        "",
        "## 자주 등장하는 재료",
    ]
    lines += [f"- {name}: {count}" for name, count in summary.get("top_materials", [])] or ["- 없음"]
    lines += ["", "## 자주 등장하는 상황"]
    lines += [f"- {name}: {count}" for name, count in summary.get("top_situations", [])] or ["- 없음"]
    lines += ["", "## 자주 등장하는 규격/성능"]
    lines += [f"- {name}: {count}" for name, count in summary.get("top_specifications", [])] or ["- 없음"]
    lines += ["", "## 건축설계 Lesson"]
    lines += [f"- {lesson}" for lesson in summary.get("lessons", [])] or ["- 아직 충분한 패턴이 없습니다."]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
