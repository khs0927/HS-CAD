from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable


@dataclass(slots=True)
class SpecificationMention:
    raw_text: str
    normalized_value: str
    unit: str
    spec_type: str
    context_text: str
    confidence: float = 0.75

    def to_dict(self) -> dict:
        return asdict(self)


PATTERNS: list[tuple[str, str, str]] = [
    (r"\b(?:THK\.?|T|t\s*=)\s*\.?\s*(\d{2,4})\b", "thickness", "mm"),
    (r"\b(\d{2,4})\s*T\b", "thickness", "mm"),
    (r"\b(\d{2,4})\s*mm\b", "length_or_thickness", "mm"),
    (r"\b(\d{3,5})\s*[xX×]\s*(\d{3,5})\b", "width_height", "mm"),
    (r"\bW\s*(\d{3,5})\s*H\s*(\d{3,5})\b", "size_wxh", "mm"),
    (r"(\d+(?:\.\d+)?)\s*W\s*/?\s*m\s*[2²]?\s*K", "thermal_transmittance", "W/m2K"),
    (r"열관류율\s*[:=]?\s*(\d+(?:\.\d+)?)", "thermal_transmittance", "W/m2K"),
    (r"(?:STC|차음성능)\s*[:=]?\s*(\d{2,3})", "acoustic_performance", "STC/dB"),
    (r"(\d{2,3})\s*dB", "acoustic_performance", "dB"),
    (r"내화\s*(\d+)\s*시간", "fire_rating", "hour"),
    (r"\bF\s*(60|90|120|180)\b", "fire_rating", "minute"),
    (r"(난연|준불연|불연|방화|단열|방수|기밀|수밀|풍압)", "performance_keyword", ""),
]


def _context(text: str, start: int, end: int, radius: int = 55) -> str:
    return text[max(0, start - radius): min(len(text), end + radius)].strip()


def _normalize(match: re.Match, spec_type: str) -> str:
    if spec_type == "size_wxh" and len(match.groups()) >= 2:
        return f"{match.group(1)}x{match.group(2)}"
    if spec_type == "performance_keyword":
        return match.group(1)
    if match.groups():
        return match.group(1)
    return match.group(0)


def extract_specifications_from_text(text: str) -> list[SpecificationMention]:
    if not text:
        return []

    results: list[SpecificationMention] = []
    seen: set[tuple[str, int]] = set()
    for pattern, spec_type, unit in PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            normalized = _normalize(match, spec_type)
            key = (spec_type + normalized, match.start())
            if key in seen:
                continue
            seen.add(key)
            results.append(
                SpecificationMention(
                    raw_text=match.group(0),
                    normalized_value=normalized,
                    unit=unit,
                    spec_type=spec_type,
                    context_text=_context(text, match.start(), match.end()),
                    confidence=0.82 if spec_type != "performance_keyword" else 0.72,
                )
            )
    return results


def extract_specifications_from_texts(texts: Iterable[str]) -> list[SpecificationMention]:
    """Extract specifications from an iterable of texts."""
    results: list[SpecificationMention] = []
    for text in texts:
        results.extend(extract_specifications_from_text(str(text)))
    return results


def extract_specifications(text: str) -> list[SpecificationMention]:
    """Compatibility wrapper expected by tests."""
    return extract_specifications_from_text(text)
