from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.ocr.vector_text_matching import normalized_text_similarity
from src.pdf_raster.pdf_raster_analysis import bbox_iou
from src.workers.provenance import build_provenance


def write_ocr_cad_text_matches(
    workspace: str | Path, *, min_score: float = 0.15
) -> dict[str, Any]:
    base = Path(workspace)
    ocr_payload = _read_json(base / "OCR_TEXT_REGIONS.json")
    ocr_regions = ocr_payload.get("regions") or []
    cad_texts = collect_cad_texts(base)
    provenance = build_provenance(
        workspace=base,
        backend="ocr_cad_text_matching",
        algorithm="canonical_cad_text_similarity_with_optional_bbox_iou_v2",
        source_artifacts=[
            str(base / "OCR_TEXT_REGIONS.json"),
            str(base / "fileized" / "json"),
        ],
        worker_name="ocr_cad_text_match",
    )
    report = build_ocr_cad_text_matches(
        ocr_regions,
        cad_texts,
        min_score=min_score,
        provenance=provenance,
    )
    out_json = base / "OCR_CAD_TEXT_MATCHES.json"
    out_report = base / "OCR_CAD_TEXT_MATCH_REPORT.md"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_report.write_text(_markdown(report), encoding="utf-8")
    return {
        "backend": "ocr_cad_text_matching",
        "status": "ok" if report["summary"]["match_count"] else "warning",
        "workspace": str(base),
        "ocr_region_count": len(ocr_regions),
        "cad_text_count": len(cad_texts),
        "match_count": report["summary"]["match_count"],
        "avg_match_score": report["summary"]["avg_match_score"],
        "artifacts": [str(out_json), str(out_report)],
        "warnings": report.get("warnings") or [],
        "provenance": provenance,
    }


def collect_cad_texts(workspace: str | Path) -> list[dict[str, Any]]:
    """Read V2 canonical text occurrences, with legacy entity fallback."""

    base = Path(workspace)
    json_dir = base / "fileized" / "json"
    rows: list[dict[str, Any]] = []
    if not json_dir.exists():
        return rows
    for path in sorted(json_dir.glob("*.json")):
        payload = _read_json(path)
        file_id = str(payload.get("file_id") or path.stem)
        relative_path = str(payload.get("relative_path") or "")
        text_rows = payload.get("texts") or []
        for text_index, row in enumerate(text_rows):
            if not isinstance(row, dict):
                continue
            text = str(row.get("plain_text") or row.get("text") or "").strip()
            if not text:
                continue
            rows.append(
                {
                    "file_id": file_id,
                    "relative_path": relative_path,
                    "source_json": str(path),
                    "text_index": text_index,
                    "occurrence_id": row.get("occurrence_id"),
                    "handle": str(row.get("handle") or ""),
                    "sub_handle": str(row.get("sub_handle") or ""),
                    "entity_type": str(row.get("entity_type") or ""),
                    "layer": str(row.get("layer") or ""),
                    "layout": str(row.get("layout") or "Model"),
                    "space": str(row.get("space") or "model"),
                    "block_path": row.get("block_path") or [],
                    "source_kind": row.get("source_kind"),
                    "text": text,
                    "normalized_text": row.get("normalized_text"),
                    "bbox": row.get("bbox"),
                    "insert": row.get("insert"),
                    "raw": row,
                }
            )
        if text_rows:
            continue
        # Backward-compatible V1 fallback. New records must use `texts`.
        entities = payload.get("entities") or []
        for entity_index, entity in enumerate(entities):
            if not isinstance(entity, dict):
                continue
            entity_type = str(
                entity.get("entity_type") or entity.get("type") or ""
            ).upper()
            if entity_type not in {"TEXT", "MTEXT"}:
                continue
            text = str(
                entity.get("text")
                or entity.get("value")
                or entity.get("content")
                or ""
            ).strip()
            if not text:
                continue
            rows.append(
                {
                    "file_id": file_id,
                    "relative_path": relative_path,
                    "source_json": str(path),
                    "entity_index": entity_index,
                    "handle": str(entity.get("handle") or ""),
                    "entity_type": entity_type,
                    "layer": str(entity.get("layer") or ""),
                    "layout": str(entity.get("layout") or "Model"),
                    "text": text,
                    "bbox": entity.get("bbox"),
                    "insert": entity.get("insert") or entity.get("position"),
                    "raw": entity,
                }
            )
    return rows


def build_ocr_cad_text_matches(
    ocr_regions: list[dict[str, Any]],
    cad_texts: list[dict[str, Any]],
    *,
    min_score: float = 0.15,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    unmatched_ocr = 0
    for ocr_index, region in enumerate(ocr_regions):
        best: dict[str, Any] | None = None
        best_score = 0.0
        best_text_similarity = 0.0
        best_bbox_iou = 0.0
        for cad_index, cad in enumerate(cad_texts):
            text_similarity = normalized_text_similarity(
                str(region.get("text") or ""), str(cad.get("text") or "")
            )
            ocr_bbox = region.get("pdf_bbox") or []
            cad_bbox = cad.get("bbox") or []
            has_bbox = (
                isinstance(ocr_bbox, list)
                and len(ocr_bbox) == 4
                and isinstance(cad_bbox, list)
                and len(cad_bbox) == 4
            )
            overlap = bbox_iou(ocr_bbox, cad_bbox) if has_bbox else 0.0
            score = round((0.80 * text_similarity) + (0.20 * overlap), 6)
            if score > best_score:
                best = dict(cad)
                best["_cad_index"] = cad_index
                best_score = score
                best_text_similarity = text_similarity
                best_bbox_iou = overlap
        if best is None or best_score < min_score:
            unmatched_ocr += 1
            continue
        matches.append(
            {
                "ocr_index": ocr_index,
                "ocr_text": region.get("text"),
                "ocr_confidence": region.get("confidence"),
                "ocr_source_pdf": region.get("source_pdf"),
                "ocr_page_index": region.get("page_index"),
                "ocr_page_contract_id": region.get("page_contract_id"),
                "ocr_pdf_bbox": region.get("pdf_bbox"),
                "cad_index": best.get("_cad_index"),
                "cad_occurrence_id": best.get("occurrence_id"),
                "cad_text": best.get("text"),
                "cad_file_id": best.get("file_id"),
                "cad_relative_path": best.get("relative_path"),
                "cad_handle": best.get("handle"),
                "cad_sub_handle": best.get("sub_handle"),
                "cad_entity_type": best.get("entity_type"),
                "cad_layer": best.get("layer"),
                "cad_layout": best.get("layout"),
                "cad_space": best.get("space"),
                "cad_block_path": best.get("block_path"),
                "cad_source_kind": best.get("source_kind"),
                "cad_bbox": best.get("bbox"),
                "text_similarity": best_text_similarity,
                "bbox_iou": best_bbox_iou,
                "match_score": best_score,
            }
        )
    avg_match_score = (
        round(
            sum(float(m.get("match_score") or 0.0) for m in matches) / len(matches),
            6,
        )
        if matches
        else 0.0
    )
    avg_text_similarity = (
        round(
            sum(float(m.get("text_similarity") or 0.0) for m in matches)
            / len(matches),
            6,
        )
        if matches
        else 0.0
    )
    avg_bbox_iou = (
        round(
            sum(float(m.get("bbox_iou") or 0.0) for m in matches) / len(matches),
            6,
        )
        if matches
        else 0.0
    )
    return {
        "backend": "ocr_cad_text_matching",
        "source": "OCR_TEXT_REGIONS+canonical_fileized_texts_v2",
        "min_score": min_score,
        "summary": {
            "ocr_region_count": len(ocr_regions),
            "cad_text_count": len(cad_texts),
            "match_count": len(matches),
            "unmatched_ocr_count": unmatched_ocr,
            "avg_match_score": avg_match_score,
            "avg_text_similarity": avg_text_similarity,
            "avg_bbox_iou": avg_bbox_iou,
        },
        "matches": matches,
        "warnings": [],
        "provenance": provenance or {},
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        "# OCR CAD Text Match Report",
        "",
        f"- Backend: `{report.get('backend')}`",
        f"- OCR region count: `{summary.get('ocr_region_count')}`",
        f"- CAD text count: `{summary.get('cad_text_count')}`",
        f"- Match count: `{summary.get('match_count')}`",
        f"- Unmatched OCR count: `{summary.get('unmatched_ocr_count')}`",
        f"- Average match score: `{summary.get('avg_match_score')}`",
        f"- Average text similarity: `{summary.get('avg_text_similarity')}`",
        f"- Average bbox IoU: `{summary.get('avg_bbox_iou')}`",
        "",
    ]
    return "\n".join(lines)
