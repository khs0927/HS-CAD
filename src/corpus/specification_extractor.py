from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(slots=True)
class SpecificationMention:
    raw_text: str
    normalized_value: str
    unit: str | None
    spec_type: str
    context_text: str
    confidence: float = 0.8


PATTERNS: list[tuple[str, str, str | None]] = [
    (r"\b(?:THK\.?|T|t\s*=?)\s*(\d{2,4})\b", "thickness", "mm"),
    (r"\b(\d{2,4})\s*T\b", "thickness", "mm"),
    (r"\b(\d{2,4})\s*mm\b", "length_or_thickness", "mm"),
    (r"\b(\d{3,5})\s*[xX×]\s*(\d{3,5})\b", "width_height", "mm"),
    (r"\bW\s*(\d{3,5})\s*H\s*(\d{3,5})\b", "width_height", "mm"),
    (r"(\d+(?:\.\d+)?)\s*W/?m2K", "thermal_transmittance", "W/m2K"),
    (r"열관류율\s*[:=]?\s*(\d+(?:\.\d+)?)", "thermal_transmittance", None),
    (r"(?:STC|차음성능)\s*[:=]?\s*(\d{1,3})\s*d?B?", "acoustic_performance", "dB"),
    (r"내화\s*(\d+)\s*시간", "fire_rating", "hour"),
    (r"\bF\s*(60|90|120|180)\b", "fire_rating", "minute"),
    (r"난연|준불연|불연|방화|단열|방수|기밀|수밀|풍압", "performance_keyword", None),
]


def extract_specifications(texts: list[str] | str) -> list[SpecificationMention]:
    if isinstance(texts, str):
        source_texts = [texts]
    else:
        source_texts = texts

    mentions: list[SpecificationMention] = []
    for text in source_texts:
        if not text:
            continue
        for pattern, spec_type, unit in PATTERNS:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                raw = match.group(0)
                start = max(0, match.start() - 40)
                end = min(len(text), match.end() + 60)
                normalized = _normalize(match, spec_type)
                mentions.append(
                    SpecificationMention(
                        raw_text=raw,
                        normalized_value=normalized,
                        unit=unit,
                        spec_type=spec_type,
                        context_text=text[start:end],
                        confidence=0.85,
                    )
                )
    return mentions


def _normalize(match: re.Match[str], spec_type: str) -> str:
    if spec_type == "width_height":
        if len(match.groups()) >= 2:
            return f"{match.group(1)}x{match.group(2)}"
    if match.groups():
        return match.group(1)
    return match.group(0)
