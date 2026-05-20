from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_ANNOTATION_STYLE = "ISO-25"
PREFERRED_ANNOTATION_STYLE = "복사 ISO-25"
DEFAULT_BATTING_LINETYPE = "BATTING"


@dataclass(frozen=True)
class CADGenerationStandards:
    """Default drafting rules used when a user does not specify alternatives."""

    annotation_style: str = DEFAULT_ANNOTATION_STYLE
    preferred_annotation_style: str = PREFERRED_ANNOTATION_STYLE
    batting_linetype: str = DEFAULT_BATTING_LINETYPE
    batting_reference_width_mm: float = 100.0
    batting_reference_scale: float = 0.08
    model_ltscale: float = 1.0
    default_text_height: float = 35.0
    dimension_layer: str = "DET_DIM"
    leader_layer: str = "DET_LEADER"
    insulation_layer: str = "DET_INSUL_100T_BATTING"
    linetype_search_paths: tuple[str, ...] = (
        r"C:\xicad\_ZWCad\zwcadiso.lin",
        r"C:\xicad\Lib\zwcadiso.lin",
    )
    notes: tuple[str, ...] = field(default_factory=lambda: (
        "Use the user-specified dimension/leader style when provided.",
        "Fallback to ISO-25; prefer 복사 ISO-25 when that style exists in the drawing.",
        "Use real dimension and leader entities, not loose line/text approximations.",
        "Use real BATTING linetype for insulation; do not draw manual wave geometry.",
        "Run scale auto-correction before saving generated drawings.",
    ))

    def batting_scale_for_width(self, width_mm: float | None) -> float:
        return recommend_batting_linetype_scale(
            width_mm=width_mm,
            reference_width_mm=self.batting_reference_width_mm,
            reference_scale=self.batting_reference_scale,
        )


def cad_unicode_escape(value: Any) -> str:
    """Return ZWCAD-friendly text for installs that lose non-ASCII COM strings."""

    out: list[str] = []
    for char in str(value):
        if ord(char) > 127:
            out.append("\\" + ("U+%04X" % ord(char)))
        else:
            out.append(char)
    return "".join(out)


def recommend_batting_linetype_scale(
    width_mm: float | None,
    reference_width_mm: float = 100.0,
    reference_scale: float = 0.08,
    minimum: float = 0.02,
    maximum: float = 1.0,
) -> float:
    """Scale BATTING so the pattern stays legible inside the insulation width."""

    if not width_mm or width_mm <= 0:
        return reference_scale
    scaled = reference_scale * (float(width_mm) / float(reference_width_mm))
    return round(max(minimum, min(maximum, scaled)), 4)


def resolve_annotation_style(
    available_styles: list[str] | tuple[str, ...] | set[str],
    requested_style: str | None = None,
    preferred_style: str = PREFERRED_ANNOTATION_STYLE,
    fallback_style: str = DEFAULT_ANNOTATION_STYLE,
) -> str:
    """Pick the annotation style for dimensions and leaders."""

    styles = {str(style).lower(): str(style) for style in available_styles if str(style).strip()}
    if requested_style and requested_style.lower() in styles:
        return styles[requested_style.lower()]
    if preferred_style.lower() in styles:
        return styles[preferred_style.lower()]
    if fallback_style.lower() in styles:
        return styles[fallback_style.lower()]
    return requested_style or fallback_style


def is_probably_broken_text(value: Any) -> bool:
    text = str(value or "")
    return bool(text) and set(text) <= {"?"}
