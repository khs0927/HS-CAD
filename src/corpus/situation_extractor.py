from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable


@dataclass(slots=True)
class SituationMention:
    tag: str
    evidence_text: str
    confidence: float = 0.7

    def to_dict(self) -> dict:
        return asdict(self)


SITUATION_RULES: dict[str, list[str]] = {
    "방음문": [r"방음문", r"차음.*문", r"STC", r"문틀", r"문짝"],
    "방음시창": [r"방음시창", r"차음.*창", r"차음.*유리", r"방음.*프레임"],
    "프로젝트창": [r"프로젝트창", r"project\s*window", r"개폐", r"열관류율"],
    "소방관진입창": [r"소방관\s*진입창", r"진입창", r"소방.*창"],
    "내화도장": [r"내화도장", r"내화.*도막", r"F\s*(60|90|120)", r"철골.*내화"],
    "판넬마감": [r"판넬", r"패널", r"후레싱", r"실란트", r"하지", r"샌드위치"],
    "H빔접합": [r"H[- ]?BEAM", r"H빔", r"철골.*접합", r"형강.*접합"],
    "외벽상세": [r"외벽", r"외장", r"마감.*상세"],
    "창호상세": [r"창호", r"창.*상세", r"WINDOW"],
    "문상세": [r"문.*상세", r"DOOR"],
    "천장마감": [r"천장", r"석고텍스", r"경량철골", r"텍스"],
    "경량철골천장": [r"경량철골", r"M[- ]?BAR", r"천장틀"],
    "석고텍스": [r"석고텍스", r"텍스"],
    "방화구획": [r"방화구획", r"방화벽", r"방화문"],
    "장애인편의시설": [r"장애인", r"BF", r"편의시설", r"경사로"],
    "학원용도변경": [r"학원", r"교육연구", r"용도변경"],
    "피난계단": [r"피난계단", r"계단", r"특별피난"],
    "화장실상세": [r"화장실", r"위생", r"TOILET"],
    "외단열": [r"외단열", r"단열재"],
    "방수상세": [r"방수", r"우레탄방수", r"시트방수"],
    "지붕상세": [r"지붕", r"ROOF"],
    "난간상세": [r"난간", r"핸드레일", r"HANDRAIL"],
}


def _context(text: str, start: int, end: int, radius: int = 60) -> str:
    return text[max(0, start - radius): min(len(text), end + radius)].strip()


def extract_situations_from_text(text: str) -> list[SituationMention]:
    if not text:
        return []

    results: list[SituationMention] = []
    seen: set[str] = set()
    for tag, patterns in SITUATION_RULES.items():
        best: SituationMention | None = None
        score = 0
        evidence = ""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                score += 1
                if not evidence:
                    evidence = _context(text, match.start(), match.end())
        if score and tag not in seen:
            seen.add(tag)
            confidence = min(0.95, 0.58 + score * 0.12)
            best = SituationMention(tag=tag, evidence_text=evidence, confidence=confidence)
            results.append(best)
    if not results:
        return [SituationMention(tag="unknown", evidence_text=text[:120], confidence=0.2)]
    return results


def extract_situations_from_texts(texts: Iterable[str]) -> list[SituationMention]:
    merged: dict[str, SituationMention] = {}
    for text in texts:
        for mention in extract_situations_from_text(str(text)):
            old = merged.get(mention.tag)
            if old is None or mention.confidence > old.confidence:
                merged[mention.tag] = mention
    return list(merged.values())


def extract_situations(text: str) -> list[SituationMention]:
    """Compatibility wrapper expected by tests."""
    return extract_situations_from_text(text)
