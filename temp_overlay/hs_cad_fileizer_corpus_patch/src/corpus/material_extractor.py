from __future__ import annotations

from dataclasses import dataclass
import re


MATERIAL_KEYWORDS: dict[str, list[str]] = {
    "concrete": ["콘크리트", "철근콘크리트", "RC"],
    "steel": ["철골", "H빔", "H-BEAM", "형강", "각파이프", "스틸", "STEEL"],
    "aluminum": ["알루미늄", "AL"],
    "stainless": ["스테인리스", "STS"],
    "glass": ["유리", "복층유리", "로이유리", "강화유리", "접합유리", "방화유리"],
    "window": ["창호", "PVC", "시스템창호", "프로젝트창", "방음시창"],
    "door": ["방음문", "목문", "철재문", "방화문"],
    "insulation": ["글라스울", "그라스울", "미네랄울", "EPS", "우레탄", "단열재"],
    "panel": ["샌드위치패널", "판넬", "패널", "징크"],
    "gypsum": ["석고보드", "방화석고보드", "석고텍스", "텍스"],
    "ceiling": ["경량철골", "천장틀"],
    "finish": ["몰탈", "타일", "페인트"],
    "waterproofing": ["방수", "우레탄방수", "시트방수"],
    "sealant": ["실란트", "코킹", "후레싱", "마감캡"],
    "acoustic": ["흡음재", "차음재"],
    "fireproofing": ["내화도장", "방청도장"],
}


@dataclass(slots=True)
class MaterialMention:
    material_name: str
    normalized_name: str
    category: str
    context_text: str
    confidence: float = 0.8
    source_text_id: str | None = None


def extract_materials(texts: list[str] | str) -> list[MaterialMention]:
    if isinstance(texts, str):
        source_texts = [texts]
    else:
        source_texts = texts

    mentions: list[MaterialMention] = []
    seen: set[tuple[str, str]] = set()

    for text in source_texts:
        if not text:
            continue
        for category, keywords in MATERIAL_KEYWORDS.items():
            for keyword in keywords:
                pattern = re.escape(keyword)
                for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                    start = max(0, match.start() - 40)
                    end = min(len(text), match.end() + 60)
                    raw = match.group(0)
                    key = (raw.lower(), text[start:end])
                    if key in seen:
                        continue
                    seen.add(key)
                    mentions.append(
                        MaterialMention(
                            material_name=raw,
                            normalized_name=keyword.lower().replace(" ", "_"),
                            category=category,
                            context_text=text[start:end],
                            confidence=0.9 if raw == keyword else 0.75,
                        )
                    )
    return mentions
