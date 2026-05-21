from __future__ import annotations

import re
from dataclasses import dataclass, field


DOOR_WIDTH_FALLBACK_CANDIDATES = (800, 850, 900, 1000)


@dataclass(frozen=True)
class ScaleCalibrationResult:
    scale: float
    source: str
    confidence: float
    candidates: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def normalize_dimension_text(text: str) -> float | None:
    raw = text.strip().lower().replace(" ", "")
    if not raw:
        return None
    raw = raw.replace(",", "")
    meter_match = re.fullmatch(r"(\d+(?:\.\d+)?)m", raw)
    if meter_match:
        return float(meter_match.group(1)) * 1000.0
    mm_match = re.fullmatch(r"(\d+(?:\.\d+)?)mm", raw)
    if mm_match:
        return float(mm_match.group(1))
    number_match = re.fullmatch(r"\d+(?:\.\d+)?", raw)
    if number_match:
        return float(raw)
    return None


def _scale_from_dimension_candidates(dimensions: list[dict]) -> ScaleCalibrationResult | None:
    candidates: list[dict] = []
    for dim in dimensions:
        value = normalize_dimension_text(str(dim.get("text", "")))
        pixel_length = float(dim.get("pixel_length", 0) or 0)
        if value and pixel_length > 0:
            scale = value / pixel_length
            candidates.append({"source": "ocr_dimension", "value_mm": value, "pixel_length": pixel_length, "scale": scale})
    if candidates:
        best = sorted(candidates, key=lambda item: item["pixel_length"], reverse=True)[0]
        return ScaleCalibrationResult(float(best["scale"]), "ocr_dimension", 0.86, candidates, [])
    return None


def _scale_from_doors(door_bboxes: list[list[float]]) -> ScaleCalibrationResult | None:
    candidates: list[dict] = []
    for bbox in door_bboxes:
        if len(bbox) != 4:
            continue
        width_px = max(abs(float(bbox[2]) - float(bbox[0])), abs(float(bbox[3]) - float(bbox[1])))
        if width_px <= 0:
            continue
        for width_mm in DOOR_WIDTH_FALLBACK_CANDIDATES:
            candidates.append({"source": "door_width_heuristic", "door_width_mm": width_mm, "pixel_width": width_px, "scale": width_mm / width_px})
    if candidates:
        # 900mm is only one candidate. Choose the median-ish candidate for stability.
        candidates_sorted = sorted(candidates, key=lambda item: item["scale"])
        best = candidates_sorted[len(candidates_sorted) // 2]
        return ScaleCalibrationResult(float(best["scale"]), "door_width_heuristic", 0.42, candidates, ["scale_from_door_fallback"])
    return None


def calibrate_scale(
    titleblock_texts: list[str] | None = None,
    dimensions: list[dict] | None = None,
    door_bboxes: list[list[float]] | None = None,
    manual_scale: float | None = None,
) -> ScaleCalibrationResult:
    candidates: list[dict] = []

    if titleblock_texts:
        for text in titleblock_texts:
            match = re.search(r"(?:scale\s*)?1\s*[:/]\s*(\d+)", text, flags=re.IGNORECASE)
            if match:
                denominator = float(match.group(1))
                candidates.append({"source": "titleblock_scale", "text": text, "drawing_scale": f"1:{int(denominator)}"})
                # Without a paper-space pixel reference this is recorded, not trusted as pixel_to_mm.

    dimension_result = _scale_from_dimension_candidates(dimensions or [])
    if dimension_result:
        return ScaleCalibrationResult(
            dimension_result.scale,
            dimension_result.source,
            dimension_result.confidence,
            candidates + dimension_result.candidates,
            dimension_result.warnings,
        )

    door_result = _scale_from_doors(door_bboxes or [])
    if door_result:
        return ScaleCalibrationResult(
            door_result.scale,
            door_result.source,
            door_result.confidence,
            candidates + door_result.candidates,
            door_result.warnings,
        )

    if manual_scale:
        return ScaleCalibrationResult(float(manual_scale), "manual", 0.95, candidates, [])

    return ScaleCalibrationResult(1.0, "identity", 0.1, candidates, ["scale_unresolved"])

