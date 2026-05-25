from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def classify_contour(*, width: float, height: float, area: float, image_area: float | None = None) -> dict[str, Any]:
    """Classify an OpenCV contour bbox into coarse drawing-analysis candidates.

    This is intentionally heuristic. It creates review evidence signals for later
    cross-validation, not final semantic truth.
    """
    w = max(float(width), 0.0)
    h = max(float(height), 0.0)
    bbox_area = w * h
    aspect_ratio = round(max(w, h) / max(min(w, h), 1.0), 6) if bbox_area else 0.0
    extent = round(float(area) / bbox_area, 6) if bbox_area else 0.0
    relative_area = round(float(area) / image_area, 8) if image_area else None

    if bbox_area <= 0 or area < 10:
        contour_class = "noise_candidate"
        confidence = 0.2
    elif aspect_ratio >= 18 and min(w, h) <= 8:
        contour_class = "line_candidate"
        confidence = 0.85
    elif w >= 80 and h >= 40 and extent <= 0.18:
        contour_class = "table_candidate"
        confidence = 0.68
    elif extent <= 0.08 and aspect_ratio < 8 and min(w, h) >= 12:
        contour_class = "rectangle_candidate"
        confidence = 0.72
    elif 0.18 <= extent <= 0.85 and min(w, h) >= 4 and max(w, h) <= 120:
        contour_class = "text_blob_candidate"
        confidence = 0.55
    else:
        contour_class = "shape_candidate"
        confidence = 0.45

    return {
        "contour_class": contour_class,
        "classification_confidence": confidence,
        "aspect_ratio": aspect_ratio,
        "extent": extent,
        "relative_area": relative_area,
    }


def classify_contour_rows(contours: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for contour in contours:
        row = dict(contour)
        classification = classify_contour(
            width=float(row.get("width") or 0.0),
            height=float(row.get("height") or 0.0),
            area=float(row.get("area") or 0.0),
            image_area=_image_area(row),
        )
        row.update(classification)
        rows.append(row)
    return rows


def contour_class_summary(contours: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    confidence_sum: dict[str, float] = {}
    for contour in contours:
        contour_class = str(contour.get("contour_class") or "unknown")
        counts[contour_class] = counts.get(contour_class, 0) + 1
        confidence_sum[contour_class] = confidence_sum.get(contour_class, 0.0) + float(contour.get("classification_confidence") or 0.0)
    avg_confidence = {
        key: round(confidence_sum.get(key, 0.0) / count, 6) if count else 0.0
        for key, count in counts.items()
    }
    return {
        "total": len(contours),
        "class_counts": counts,
        "avg_confidence_by_class": avg_confidence,
    }


def postprocess_raster_contours(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    path = base / "RASTER_CONTOURS.json"
    if not path.exists():
        return {"status": "missing", "reason": f"not found: {path}", "summary": {"total": 0, "class_counts": {}}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    contours = classify_contour_rows(payload.get("contours") or [])
    summary = contour_class_summary(contours)
    payload["contours"] = contours
    payload["class_summary"] = summary
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out = {
        "backend": "pdf_raster_contour_classification",
        "status": "ok",
        "summary": summary,
        "artifact": str(path),
    }
    (base / "RASTER_CONTOUR_CLASSES.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _image_area(row: dict[str, Any]) -> float | None:
    return None
