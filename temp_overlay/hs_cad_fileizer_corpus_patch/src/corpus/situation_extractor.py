from __future__ import annotations

from dataclasses import dataclass
import re


SITUATION_RULES: dict[str, list[str]] = {
    "방음문": ["방음문", "차음", "STC", "문틀", "문짝"],
    "방음시창": ["방음시창", "차음", "유리", "프레임", "STC"],
    "프로젝트창": ["프로젝트창", "열관류율", "창호", "개폐"],
    "소방관진입창": ["소방관 진입창", "진입창", "소방"],
    "내화도장": ["내화도장", "내화", "철골", "도막"],
    "판넬마감": ["판넬", "패널", "후레싱", "실란트", "하지", "피스"],
    "H빔접합": ["H-BEAM", "H빔", "철골", "접합", "형강"],
    "천장마감": ["경량철골", "석고텍스", "천장", "천장고"],
    "방화구획": ["방화구획", "방화문", "방화유리"],
    "장애인편의시설": ["장애인", "무장애", "BF", "경사로"],
    "학원용도변경": ["학원", "교육연구시설", "용도변경"],
    "화장실상세": ["화장실", "위생도기", "장애인화장실"],
    "외단열": ["외단열", "단열재", "열교"],
    "방수상세": ["방수", "우레탄방수", "시트방수"],
    "지붕상세": ["지붕", "루프", "방수층"],
    "난간상세": ["난간", "핸드레일"],
}


@dataclass(slots=True)
class SituationMention:
    tag: str
    evidence_text: str
    matched_keywords: list[str]
    confidence: float


def extract_situations(texts: list[str] | str) -> list[SituationMention]:
    if isinstance(texts, str):
        joined = texts
    else:
        joined = "\n".join(t for t in texts if t)

    mentions: list[SituationMention] = []
    for tag, keywords in SITUATION_RULES.items():
        matched: list[str] = []
        for keyword in keywords:
            if re.search(re.escape(keyword), joined, flags=re.IGNORECASE):
                matched.append(keyword)
        if matched:
            idx = min([joined.lower().find(k.lower()) for k in matched if joined.lower().find(k.lower()) >= 0] or [0])
            context = joined[max(0, idx - 80): idx + 160]
            confidence = min(0.95, 0.45 + 0.15 * len(matched))
            mentions.append(SituationMention(tag=tag, evidence_text=context, matched_keywords=matched, confidence=confidence))
    return mentions
