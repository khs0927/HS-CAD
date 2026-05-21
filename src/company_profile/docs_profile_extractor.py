from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(slots=True)
class ExtractedRule:
    rule_type: str
    value: str
    source_file: str
    evidence_text: str
    confidence: float


KEYWORDS = {
    "titleblock": ["ZIUM_sheet_architect", "도곽", "도각", "title sheet", "titleblock"],
    "layer": ["WAL1", "WALL1", "COL", "COLU", "중심선", "치수"],
    "dimension": ["300DIM", "DimStyle", "치수 스타일", "DIMENSION"],
    "text_style": ["지움EB", "문자", "글씨", "text height"],
    "policy": ["레이어 무변경", "주변 속성", "preview", "dry-run", "자동 저장 금지", "도곽 재사용"],
}


def extract_rules_from_text(path: Path, text: str) -> list[ExtractedRule]:
    rules: list[ExtractedRule] = []
    for rule_type, keywords in KEYWORDS.items():
        for keyword in keywords:
            for m in re.finditer(re.escape(keyword), text, flags=re.IGNORECASE):
                start = max(0, m.start() - 80)
                end = min(len(text), m.end() + 120)
                rules.append(ExtractedRule(rule_type, m.group(0), str(path), text[start:end], 0.8))
    return rules
