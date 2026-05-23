from __future__ import annotations

from typing import Any


def classify_contour(*, width: float, height: float, area: float, image_area: float | None = None) -> dict[str, Any]:
    """Classify an OpenCV contour bbox into coarse drawing-analysis candidates.

    This is intentionally heuristic. It creates evidence signals for later
    cross-validation, not final semantic truth.
    """
    w = max(float(width), 0.0)
    h = max(float(height), 0.0)
    bbox_area = w * h
    aspect_ratio = round(max(w, h) / max(min(w, h), 1.0), 6) if bbox_area else 0.0
    extent = round(float(area) / bbox_area, 6) if bbox_area else 0.0
    relative_area = round(float(area) / image_area, 8) if image_area else None

    if bbox_area <= 0 or area < 10:
        contour_class = 'noise_candidate'
        confidence = 0.2
    elif aspect_ratio >= 18 and min(w, h) <= 8:
        contour_class = 'line_candidate'
        confidence = 0.85
    elif w >= 80 and h >= 40 and extent <= 0.18:
        contour_class = 'table_candidate'
        confidence = 0.68
    elif extent <= 0.08 and aspect_ratio < 8 and min(w, h) >= 12:
        contour_class = 'rectangle_candidate'
        confidence = 0.72
    elif 0.18 <= extent <= 0.85 and min(w, h) >= 4 and max(w, h) <= 120:
        contour_class = 'text_blob_candidate'
        confidence = 0.55
    else:
        contour_class = 'shape_candidate'
        confidence = 0.45

    return {
        'contour_class': contour_class,
        'classification_confidence': confidence,
        'aspect_ratio': aspect_ratio,
        'extent': extent,
        'relative_area': relative_area,
    }


def contour_class_summary(contours: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for contour in contours:
        contour_class = str(contour.get('contour_class') or 'unknown')
        counts[contour_class] = counts.get(contour_class, 0) + 1
    return {
        'total': len(contours),
        'class_counts': counts,
    }
