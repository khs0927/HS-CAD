"""Domain-aware query expansion for architectural drawing corpus search.

This module is dependency-free and intentionally conservative. It expands Korean
and English construction/CAD terms into common aliases so the SQLite search layer
can find more relevant evidence without needing an embedding model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


DOMAIN_SYNONYMS: dict[str, list[str]] = {
    "판넬": ["패널", "샌드위치패널", "panel", "sandwich panel", "외벽판넬", "글라스울패널", "EPS패널", "EPS판넬"],
    "패널": ["판넬", "샌드위치패널", "panel"],
    "글라스울": ["그라스울", "glasswool", "glass wool", "미네랄울", "mineral wool"],
    "h빔": ["H-BEAM", "H BEAM", "H형강", "철골", "steel beam", "beam"],
    "h-beam": ["H빔", "H형강", "철골", "steel beam"],
    "철골": ["H빔", "H-BEAM", "형강", "steel", "structural steel"],
    "방음": ["차음", "흡음", "soundproof", "acoustic", "STC", "dB"],
    "방음문": ["차음문", "soundproof door", "acoustic door", "STC", "문틀", "문짝"],
    "방음시창": ["차음시창", "soundproof window", "acoustic window", "STC", "유리", "프레임"],
    "프로젝트창": ["project window", "창호", "개폐", "열관류율", "U-value"],
    "내화": ["내화도장", "방화", "fireproof", "fire resistance", "F60", "F120", "도막"],
    "내화도장": ["내화", "철골", "도막", "fireproof paint", "fireproofing"],
    "천장": ["경량철골", "석고텍스", "ceiling", "천장고", "텍스"],
    "석고텍스": ["텍스", "ceiling tile", "천장재"],
    "실란트": ["코킹", "sealant", "caulking", "실링"],
    "코킹": ["실란트", "sealant", "caulking"],
    "후레싱": ["flashing", "마감캡", "캡", "물끊기"],
    "열관류율": ["U-value", "u value", "W/m2K", "단열"],
    "소방관진입창": ["소방관 진입창", "진입창", "소방", "firefighter access"],
}

TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣_.+\-/]+", re.UNICODE)


@dataclass
class ExpandedQuery:
    original: str
    tokens: list[str] = field(default_factory=list)
    expanded_terms: list[str] = field(default_factory=list)

    @property
    def all_terms(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for term in [*self.tokens, *self.expanded_terms]:
            norm = normalize_token(term)
            if norm and norm not in seen:
                seen.add(norm)
                out.append(norm)
        return out


def normalize_token(token: str) -> str:
    token = token.strip().lower()
    token = token.replace("㎡", "m2").replace("㎜", "mm")
    token = token.strip(" ,.;:()[]{}<>\"'")
    return token


def tokenize(text: str) -> list[str]:
    return [normalize_token(m.group(0)) for m in TOKEN_RE.finditer(text or "") if normalize_token(m.group(0))]


def expand_query(query: str, max_terms: int = 64) -> ExpandedQuery:
    tokens = tokenize(query)
    expanded: list[str] = []

    for token in tokens:
        # direct match
        if token in DOMAIN_SYNONYMS:
            expanded.extend(DOMAIN_SYNONYMS[token])

        # loose match for Korean phrases with spaces removed
        compact = token.replace(" ", "")
        if compact in DOMAIN_SYNONYMS:
            expanded.extend(DOMAIN_SYNONYMS[compact])

        # substring match for common terms
        for key, values in DOMAIN_SYNONYMS.items():
            if key in token or token in key:
                expanded.extend(values)

    result = ExpandedQuery(original=query, tokens=tokens, expanded_terms=[])
    seen = set(result.tokens)
    for term in expanded:
        norm = normalize_token(term)
        if norm and norm not in seen:
            result.expanded_terms.append(norm)
            seen.add(norm)
        if len(result.all_terms) >= max_terms:
            break
    return result
