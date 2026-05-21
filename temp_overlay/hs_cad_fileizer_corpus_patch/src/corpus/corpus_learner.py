from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


def learn_from_corpus(db_path: Path, *, top_n: int = 20) -> dict[str, Any]:
    db_path = Path(db_path)
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        materials = [r["material_name"] for r in con.execute("SELECT material_name FROM materials")]
        situations = [r["tag"] for r in con.execute("SELECT tag FROM situations")]
        specs = [r["raw_text"] for r in con.execute("SELECT raw_text FROM specifications")]

    summary = {
        "top_materials": Counter(materials).most_common(top_n),
        "top_situations": Counter(situations).most_common(top_n),
        "top_specifications": Counter(specs).most_common(top_n),
        "lessons": [],
    }
    tags = set(situations)
    if "방음시창" in tags:
        summary["lessons"].append("방음시창 상세에서는 창호 크기, 프레임, 유리 사양, 실링, 차음성능 표기가 함께 등장하는 경향이 있다.")
    if "판넬마감" in tags or "H빔접합" in tags:
        summary["lessons"].append("판넬-H빔 접합 상세에서는 판넬 두께, 하지철물, 후레싱, 실란트, 고정 피스 표현이 함께 나타난다.")
    if "천장마감" in tags:
        summary["lessons"].append("천장 마감 검토에서는 경량철골 천장틀, 석고텍스, 보 하부 높이, 마감 여유 공간, 최종 천장고를 함께 확인한다.")
    return summary
