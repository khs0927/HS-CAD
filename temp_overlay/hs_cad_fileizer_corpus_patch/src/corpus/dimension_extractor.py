from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(slots=True)
class DimensionMention:
    raw_text: str
    value: str
    unit: str | None
    role: str
    context_text: str
    confidence: float = 0.75


DIM_PATTERNS = [
    (r"\b(\d{3,5})\s*[xX×]\s*(\d{3,5})\b", "size_2d", "mm"),
    (r"\bW\s*(\d{3,5})\s*H\s*(\d{3,5})\b", "size_2d", "mm"),
    (r"천장고\s*[:=]?\s*(\d{3,5})", "ceiling_height", "mm"),
    (r"층고\s*[:=]?\s*(\d{3,5})", "floor_height", "mm"),
    (r"(?:개구부|OPENING)\s*[:=]?\s*(\d{3,5})", "opening_width", "mm"),
    (r"(?:THK\.?|T|t\s*=?)\s*(\d{2,4})", "thickness", "mm"),
    (r"(\d{2,4})\s*T\b", "thickness", "mm"),
    (r"EL\.?\s*[+-]?\s*\d+(?:\.\d+)?", "level", None),
]


def extract_dimensions(texts: list[str] | str) -> list[DimensionMention]:
    if isinstance(texts, str):
        source_texts = [texts]
    else:
        source_texts = texts

    mentions: list[DimensionMention] = []
    for text in source_texts:
        if not text:
            continue
        for pattern, role, unit in DIM_PATTERNS:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                raw = match.group(0)
                start = max(0, match.start() - 40)
                end = min(len(text), match.end() + 60)
                value = "x".join(match.groups()) if len(match.groups()) >= 2 else (match.group(1) if match.groups() else raw)
                mentions.append(DimensionMention(raw, value, unit, role, text[start:end]))
    return mentions
