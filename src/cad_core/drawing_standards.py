from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any


DEFAULT_ANNOTATION_STYLE = "ISO-25"
PREFERRED_ANNOTATION_STYLE = "복사 ISO-25"
DEFAULT_BATTING_LINETYPE = "BATTING"
Point2D = tuple[float, float]


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
    default_dimension_scale: float = 15.0
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
        "Do not override dimension text; dimensions must display the measured geometry.",
        "Use QLEADER-style leader entities with an L route and a horizontal landing next to text.",
        "Treat insulation as an area; generate the batting pattern on the thickness centerline.",
        "Avoid raw BATTING linetype when thickness-fit is required; use generated pattern geometry.",
        "Run annotation collision checks before saving generated drawings.",
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


def measured_dimension_override() -> str:
    """Return the only allowed override for generated dimensions."""

    return ""


def format_measured_dimension(length_mm: float) -> str:
    """Format a measured dimension value without inventing replacement labels."""

    value = float(length_mm)
    if abs(value - round(value)) < 1e-6:
        return f"{int(round(value)):,}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def text_box_width(value: Any, height: float) -> float:
    """Approximate CAD text width for annotation collision checks."""

    width = 0.0
    for char in str(value):
        width += float(height) * (0.86 if ord(char) > 127 else 0.55)
    return width


def qleader_l_route_points(
    target: Point2D,
    label_origin: Point2D,
    label_width: float,
    label_height: float,
    landing_gap: float = 18.0,
) -> list[Point2D]:
    """Return QLEADER points for target -> vertical leg -> horizontal text landing."""

    tx, ty = float(target[0]), float(target[1])
    lx, ly = float(label_origin[0]), float(label_origin[1])
    landing_y = ly + float(label_height) * 0.45
    if lx >= tx:
        landing_x = lx - float(landing_gap)
    else:
        landing_x = lx + float(label_width) + float(landing_gap)
    return [(tx, ty), (tx, landing_y), (landing_x, landing_y)]


def insulation_centerline(
    origin: Point2D,
    thickness_mm: float,
    length_mm: float,
    *,
    vertical: bool = True,
) -> tuple[Point2D, Point2D]:
    """Return the centerline of an insulation area."""

    x, y = float(origin[0]), float(origin[1])
    thickness = float(thickness_mm)
    length = float(length_mm)
    if vertical:
        cx = x + thickness / 2.0
        return (cx, y), (cx, y + length)
    cy = y + thickness / 2.0
    return (x, cy), (x + length, cy)


def insulation_batting_pattern_points(
    origin: Point2D,
    thickness_mm: float,
    length_mm: float,
    *,
    vertical: bool = True,
    margin_ratio: float = 0.12,
    min_margin_mm: float = 8.0,
    min_amplitude_mm: float = 4.0,
    min_pitch_mm: float = 24.0,
    pitch_ratio: float = 0.45,
) -> list[Point2D]:
    """Generate a thickness-fit insulation batting pattern on the centerline."""

    x, y = float(origin[0]), float(origin[1])
    thickness = float(thickness_mm)
    length = float(length_mm)
    if thickness <= 0 or length <= 0:
        return []

    margin = max(float(min_margin_mm), thickness * float(margin_ratio))
    amplitude = max(float(min_amplitude_mm), thickness / 2.0 - margin)
    pitch = max(float(min_pitch_mm), thickness * float(pitch_ratio))
    steps = max(4, int(math.ceil(length / pitch)))
    actual_pitch = length / steps

    points: list[Point2D] = []
    for index in range(steps + 1):
        offset = -amplitude if index % 2 == 0 else amplitude
        if vertical:
            points.append((x + thickness / 2.0 + offset, y + index * actual_pitch))
        else:
            points.append((x + index * actual_pitch, y + thickness / 2.0 + offset))
    return points


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
