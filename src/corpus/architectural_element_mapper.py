from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable


@dataclass(slots=True)
class CanonicalElementMention:
    canonical_element: str
    evidence: str
    source_kind: str
    confidence: float = 0.65

    def to_dict(self) -> dict:
        return asdict(self)


ELEMENT_RULES: dict[str, list[str]] = {
    "WALL": [r"wall", r"벽", r"칸막이", r"partition", r"WAL"],
    "COLUMN": [r"col", r"column", r"기둥", r"COLU"],
    "BEAM": [r"beam", r"보\b", r"H[- ]?BEAM", r"H빔"],
    "SLAB": [r"slab", r"슬라브"],
    "DOOR": [r"door", r"문\b", r"\bD\d+"],
    "WINDOW": [r"window", r"win", r"창", r"창호", r"\bW\d+"],
    "STAIR": [r"stair", r"계단"],
    "RAMP": [r"ramp", r"경사로"],
    "ELEVATOR": [r"elevator", r"승강기", r"엘리베이터", r"\bEV\b"],
    "TOILET": [r"toilet", r"화장실", r"위생"],
    "DIMENSION": [r"dim", r"치수", r"300DIM"],
    "GRID": [r"grid", r"그리드"],
    "CENTERLINE": [r"center", r"centre", r"중심선", r"CEN"],
    "SECTION_MARK": [r"section", r"단면"],
    "ELEVATION_MARK": [r"elev", r"입면"],
    "DETAIL_MARK": [r"detail", r"상세"],
    "TITLE_BLOCK": [r"title", r"도곽", r"도각", r"sheet"],
    "MATERIAL_NOTE": [r"재료", r"material", r"마감"],
    "FINISH_NOTE": [r"finish", r"마감"],
    "FIRE_SAFETY": [r"fire", r"방화", r"내화", r"소방"],
    "ACOUSTIC": [r"sound", r"방음", r"차음", r"흡음", r"STC"],
    "THERMAL_INSULATION": [r"insulation", r"단열", r"열관류율"],
    "WATERPROOFING": [r"waterproof", r"방수"],
    "STRUCTURAL_STEEL": [r"steel", r"철골", r"H[- ]?BEAM", r"H빔", r"형강"],
    "PANEL_SYSTEM": [r"panel", r"판넬", r"패널", r"후레싱"],
    "CEILING_SYSTEM": [r"ceiling", r"천장", r"경량철골", r"석고텍스"],
    "FLOOR_FINISH": [r"floor", r"바닥", r"타일"],
}


def map_text_to_elements(text: str, source_kind: str = "text") -> list[CanonicalElementMention]:
    if not text:
        return []

    results: list[CanonicalElementMention] = []
    for element, patterns in ELEMENT_RULES.items():
        score = 0
        evidence = None
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                score += 1
                evidence = match.group(0)
        if score:
            results.append(
                CanonicalElementMention(
                    canonical_element=element,
                    evidence=evidence or text[:80],
                    source_kind=source_kind,
                    confidence=min(0.95, 0.55 + score * 0.12),
                )
            )
    if not results:
        return [CanonicalElementMention(canonical_element="UNKNOWN", evidence=text[:80], source_kind=source_kind, confidence=0.15)]
    return results


def map_many_to_elements(items: Iterable[str], source_kind: str = "text") -> list[CanonicalElementMention]:
    merged: dict[str, CanonicalElementMention] = {}
    for item in items:
        for mention in map_text_to_elements(str(item), source_kind=source_kind):
            old = merged.get(mention.canonical_element)
            if old is None or mention.confidence > old.confidence:
                merged[mention.canonical_element] = mention
    return list(merged.values())


def map_to_canonical_elements(values: list[str] | str, *, source_field: str = "unknown") -> list[CanonicalElementMention]:
    """Compatibility wrapper expected by tests.

    Accepts a single string or a list of strings and returns a list of
    :class:`CanonicalElementMention` objects, delegating to
    :func:`map_many_to_elements`. ``source_field`` is mapped to the underlying
    ``source_kind`` argument.
    """
    if isinstance(values, str):
        vals = [values]
    else:
        vals = [v for v in values if v]
    return map_many_to_elements(vals, source_kind=source_field)
