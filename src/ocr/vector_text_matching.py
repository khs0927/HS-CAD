from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from typing import Any

from src.pdf_raster.pdf_raster_analysis import bbox_iou
from src.workers.provenance import build_provenance


def write_ocr_vector_text_matches(workspace: str | Path, *, min_score: float = 0.15) -> dict[str, Any]:
    base = Path(workspace)
    ocr_payload = _read_json(base / 'OCR_TEXT_REGIONS.json')
    vector_payload = _read_json(base / 'PDF_VECTOR_OBJECTS.json')
    ocr_regions = ocr_payload.get('regions') or []
    vector_objects = [obj for obj in vector_payload.get('objects') or [] if _has_vector_text(obj)]
    provenance = build_provenance(
        workspace=base,
        backend='ocr_vector_text_matching',
        algorithm='bbox_iou_plus_text_similarity',
        source_artifacts=[str(base / 'OCR_TEXT_REGIONS.json'), str(base / 'PDF_VECTOR_OBJECTS.json')],
        worker_name='ocr_vector_text_match',
    )
    report = build_ocr_vector_text_matches(ocr_regions, vector_objects, min_score=min_score, provenance=provenance)
    out_json = base / 'OCR_VECTOR_TEXT_MATCHES.json'
    out_report = base / 'OCR_VECTOR_TEXT_MATCH_REPORT.md'
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    out_report.write_text(_markdown(report), encoding='utf-8')
    return {
        'backend': 'ocr_vector_text_matching',
        'status': 'ok' if report['summary']['match_count'] else 'warning',
        'workspace': str(base),
        'ocr_region_count': len(ocr_regions),
        'vector_text_count': len(vector_objects),
        'match_count': report['summary']['match_count'],
        'avg_match_score': report['summary']['avg_match_score'],
        'artifacts': [str(out_json), str(out_report)],
        'warnings': report.get('warnings') or [],
        'provenance': provenance,
    }


def build_ocr_vector_text_matches(
    ocr_regions: list[dict[str, Any]],
    vector_objects: list[dict[str, Any]],
    *,
    min_score: float = 0.15,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    vector_by_page: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for vector in vector_objects:
        key = _page_key(vector)
        vector_by_page.setdefault(key, []).append(vector)

    matches: list[dict[str, Any]] = []
    unmatched_ocr = 0
    for ocr_index, region in enumerate(ocr_regions):
        candidates = vector_by_page.get(_page_key(region), [])
        best: dict[str, Any] | None = None
        best_score = 0.0
        best_iou = 0.0
        best_text_similarity = 0.0
        for vector_index, vector in enumerate(candidates):
            iou = bbox_iou(region.get('pdf_bbox') or [], vector.get('pdf_bbox') or [])
            text_similarity = normalized_text_similarity(str(region.get('text') or ''), str(vector.get('text') or ''))
            score = round((0.65 * iou) + (0.35 * text_similarity), 6)
            if score > best_score:
                best = dict(vector)
                best['_candidate_index'] = vector_index
                best_score = score
                best_iou = iou
                best_text_similarity = text_similarity
        if best is None or best_score < min_score:
            unmatched_ocr += 1
            continue
        matches.append({
            'ocr_index': ocr_index,
            'ocr_text': region.get('text'),
            'ocr_confidence': region.get('confidence'),
            'vector_text': best.get('text'),
            'source_pdf': region.get('source_pdf'),
            'page_index': region.get('page_index'),
            'page_contract_id': region.get('page_contract_id'),
            'ocr_pdf_bbox': region.get('pdf_bbox'),
            'vector_pdf_bbox': best.get('pdf_bbox'),
            'bbox_iou': best_iou,
            'text_similarity': best_text_similarity,
            'match_score': best_score,
            'vector_object_type': best.get('object_type'),
            'vector_index_on_page': best.get('_candidate_index'),
        })
    avg_match_score = round(sum(float(m.get('match_score') or 0.0) for m in matches) / len(matches), 6) if matches else 0.0
    avg_text_similarity = round(sum(float(m.get('text_similarity') or 0.0) for m in matches) / len(matches), 6) if matches else 0.0
    avg_bbox_iou = round(sum(float(m.get('bbox_iou') or 0.0) for m in matches) / len(matches), 6) if matches else 0.0
    return {
        'backend': 'ocr_vector_text_matching',
        'source': 'OCR_TEXT_REGIONS+PDF_VECTOR_OBJECTS',
        'min_score': min_score,
        'summary': {
            'ocr_region_count': len(ocr_regions),
            'vector_text_count': len(vector_objects),
            'match_count': len(matches),
            'unmatched_ocr_count': unmatched_ocr,
            'avg_match_score': avg_match_score,
            'avg_text_similarity': avg_text_similarity,
            'avg_bbox_iou': avg_bbox_iou,
        },
        'matches': matches,
        'warnings': [],
        'provenance': provenance or {},
    }


def normalized_text_similarity(a: str, b: str) -> float:
    left = _normalize_text(a)
    right = _normalize_text(b)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return round(difflib.SequenceMatcher(None, left, right).ratio(), 6)


def _normalize_text(value: str) -> str:
    return re.sub(r'\s+', '', value or '').strip().lower()


def _has_vector_text(obj: dict[str, Any]) -> bool:
    return bool(str(obj.get('text') or '').strip())


def _page_key(obj: dict[str, Any]) -> tuple[str, int, str]:
    return (str(obj.get('source_pdf') or ''), int(obj.get('page_index') or 0), str(obj.get('page_contract_id') or ''))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _markdown(report: dict[str, Any]) -> str:
    summary = report.get('summary') or {}
    lines = [
        '# OCR Vector Text Match Report',
        '',
        f"- Backend: `{report.get('backend')}`",
        f"- OCR region count: `{summary.get('ocr_region_count')}`",
        f"- Vector text count: `{summary.get('vector_text_count')}`",
        f"- Match count: `{summary.get('match_count')}`",
        f"- Unmatched OCR count: `{summary.get('unmatched_ocr_count')}`",
        f"- Average match score: `{summary.get('avg_match_score')}`",
        f"- Average text similarity: `{summary.get('avg_text_similarity')}`",
        f"- Average bbox IoU: `{summary.get('avg_bbox_iou')}`",
        '',
    ]
    return '\n'.join(lines)
