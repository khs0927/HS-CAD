from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable


@dataclass(slots=True)
class DimensionMention:
    raw_text: str
    role: str
    value: str
    unit: str
    context_text: str
    confidence: float = 0.7

    def to_dict(self) -> dict:
        return asdict(self)


ROLE_HINTS = [
    ("size_2d", [r"\b\d{3,5}\s*[xX×]\s*\d{3,5}\b"]),
    ("ceiling_height", [r"천장고", r"CH", r"ceiling", r"\b\d{3,4}\b"]),
    ("floor_height", [r"층고", r"FL", r"floor height"]),
    ("door_size", [r"방화문", r"방음문", r"문", r"DOOR", r"\bD\d"]),
    ("window_size", [r"창", r"창호", r"방음시창", r"프로젝트창", r"WINDOW", r"\bW\d"]),
    ("panel_thickness", [r"판넬", r"패널", r"샌드위치", r"글라스울", r"EPS"]),
    ("thickness", [r"벽", r"wall", r"THK", r"두께"]),
    ("opening_width", [r"개구부", r"opening"]),
    ("level", [r"레벨", r"LEVEL", r"EL\.?", r"SL\.?", r"FL\.?"]),
]


def _context(text: str, start: int, end: int, radius: int = 60) -> str:
    return text[max(0, start - radius): min(len(text), end + radius)].strip()


def _infer_role(text: str) -> str:
    for role, patterns in ROLE_HINTS:
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return role
    return "unknown"


def extract_dimensions_from_text(text: str) -> list[DimensionMention]:
    if not text:
        return []

    patterns = [
        (r"\b(\d{3,5})\s*[xX×]\s*(\d{3,5})\b", "mm"),
        (r"\bW\s*(\d{3,5})\s*H\s*(\d{3,5})\b", "mm"),
        (r"\b(?:THK\.?|T|t\s*=)\s*(\d{2,4})\b", "mm"),
        (r"\b(\d{2,4})\s*T\b", "mm"),
    (r"\b(\d{3,5})\s*mm\b", "mm"),
    (r"\b(\d{3,4})\b", "mm"),
    (r"[+\-]?\d+\.\d{2,3}", "level"),
]
    results: list[DimensionMention] = []
    seen: set[tuple[str, int]] = set()
    for pattern, unit in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            raw = match.group(0)
            ctx = _context(text, match.start(), match.end())
            if (raw, match.start()) in seen:
                continue
            seen.add((raw, match.start()))
            if len(match.groups()) >= 2:
                value = f"{match.group(1)}x{match.group(2)}"
            elif match.groups():
                value = match.group(1)
            else:
                value = raw
            results.append(
                DimensionMention(
                    raw_text=raw,
                    role=_infer_role(raw),
                    value=value,
                    unit=unit,
                    context_text=ctx,
                    confidence=0.78,
                )
            )
    return results


def extract_dimensions_from_texts(texts: Iterable[str]) -> list[DimensionMention]:
    results: list[DimensionMention] = []
    for text in texts:
        results.extend(extract_dimensions_from_text(str(text)))
    return results


def extract_dimensions(text: str) -> list[DimensionMention]:
    """Compatibility wrapper expected by tests."""
    return extract_dimensions_from_text(text)
