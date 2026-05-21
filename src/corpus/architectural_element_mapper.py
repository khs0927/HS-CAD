from __future__ import annotations

from dataclasses import dataclass
import re


ELEMENT_KEYWORDS: dict[str, list[str]] = {
    "WALL": ["wall", "벽", "칸막이", "partition", "WAL"],
    "COLUMN": ["col", "column", "기둥", "COL"],
    "BEAM": ["beam", "보", "hbeam", "h-beam", "H빔"],
    "SLAB": ["slab", "슬라브"],
    "DOOR": ["door", "문", "D1", "방화문", "방음문"],
    "WINDOW": ["window", "창", "W1", "WIN", "창호", "프로젝트창"],
    "STAIR": ["stair", "계단"],
    "DIMENSION": ["dim", "dimension", "치수"],
    "GRID": ["grid", "축열", "그리드"],
    "CENTERLINE": ["center", "centre", "중심선", "CEN"],
    "TITLE_BLOCK": ["title", "도곽", "도각", "sheet"],
    "FIRE_SAFETY": ["fire", "방화", "내화", "소방"],
    "ACOUSTIC": ["sound", "방음", "차음", "흡음"],
    "THERMAL_INSULATION": ["insulation", "단열", "열관류율"],
    "WATERPROOFING": ["waterproof", "방수"],
    "STRUCTURAL_STEEL": ["steel", "철골", "H-BEAM", "H빔", "형강"],
    "PANEL_SYSTEM": ["panel", "판넬", "패널", "샌드위치패널"],
    "CEILING_SYSTEM": ["ceiling", "천장", "텍스", "경량철골"],
    "FLOOR_FINISH": ["floor", "바닥", "마루", "타일"],
}


@dataclass(slots=True)
class CanonicalElementMention:
    canonical_element: str
    evidence: str
    source_field: str
    confidence: float


def map_to_canonical_elements(values: list[str] | str, *, source_field: str = "unknown") -> list[CanonicalElementMention]:
    if isinstance(values, str):
        vals = [values]
    else:
        vals = [v for v in values if v]

    out: list[CanonicalElementMention] = []
    seen: set[tuple[str, str]] = set()

    for value in vals:
        for canonical, keywords in ELEMENT_KEYWORDS.items():
            for keyword in keywords:
                if re.search(re.escape(keyword), value, flags=re.IGNORECASE):
                    key = (canonical, value)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(CanonicalElementMention(canonical, value, source_field, 0.8))
                    break
    return out
