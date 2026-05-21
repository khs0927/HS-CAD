from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WallThicknessResult:
    thickness: float | None
    source: str
    confidence: float
    candidates: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def estimate_wall_thickness(
    double_line_candidates: list | None = None,
    polygon_thicknesses: list[float] | None = None,
    fallback_candidates: tuple[int, int, int] = (100, 150, 200),
) -> WallThicknessResult:
    candidates: list[dict] = []
    if double_line_candidates:
        best = max(double_line_candidates, key=lambda c: getattr(c, "confidence", 0.0))
        thickness = float(getattr(best, "spacing", 0.0))
        candidates.append({"source": "double_line_detector", "thickness": thickness})
        return WallThicknessResult(thickness, "double_line_detector", 0.82, candidates, [])

    if polygon_thicknesses:
        thickness = float(sorted(polygon_thicknesses)[len(polygon_thicknesses) // 2])
        candidates.append({"source": "raster2seq_polygon", "thickness": thickness})
        return WallThicknessResult(thickness, "raster2seq_polygon", 0.68, candidates, [])

    for value in fallback_candidates:
        candidates.append({"source": "standard_fallback", "thickness": value})
    if fallback_candidates:
        return WallThicknessResult(float(fallback_candidates[1]), "standard_fallback", 0.35, candidates, ["wall_thickness_fallback"])
    return WallThicknessResult(None, "unresolved", 0.0, candidates, ["wall_thickness_unresolved"])

