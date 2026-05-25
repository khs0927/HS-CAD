from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.workers.provenance import build_provenance


def write_text_evidence_fusion(workspace: str | Path, *, review_threshold: float = 0.55, conflict_threshold: float = 0.35) -> dict[str, Any]:
    base = Path(workspace)
    ocr_payload = _read_json(base / 'OCR_TEXT_REGIONS.json')
    vector_payload = _read_json(base / 'OCR_VECTOR_TEXT_MATCHES.json')
    cad_payload = _read_json(base / 'OCR_CAD_TEXT_MATCHES.json')
    ocr_regions = ocr_payload.get('regions') or []
    vector_matches = vector_payload.get('matches') or []
    cad_matches = cad_payload.get('matches') or []
    provenance = build_provenance(
        workspace=base,
        backend='text_evidence_fusion',
        algorithm='weighted_text_evidence_score_v1',
        source_artifacts=[
            str(base / 'OCR_TEXT_REGIONS.json'),
            str(base / 'OCR_VECTOR_TEXT_MATCHES.json'),
            str(base / 'OCR_CAD_TEXT_MATCHES.json'),
        ],
        worker_name='text_evidence_fusion',
    )
    report = build_text_evidence_fusion(
        ocr_regions,
        vector_matches,
        cad_matches,
        review_threshold=review_threshold,
        conflict_threshold=conflict_threshold,
        provenance=provenance,
    )
    out_json = base / 'TEXT_EVIDENCE_FUSION.json'
    out_report = base / 'TEXT_EVIDENCE_FUSION_REPORT.md'
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    out_report.write_text(_markdown(report), encoding='utf-8')
    return {
        'backend': 'text_evidence_fusion',
        'status': 'ok' if report['summary']['item_count'] else 'warning',
        'workspace': str(base),
        'item_count': report['summary']['item_count'],
        'review_required_count': report['summary']['review_required_count'],
        'avg_confidence': report['summary']['avg_confidence'],
        'artifacts': [str(out_json), str(out_report)],
        'warnings': report.get('warnings') or [],
        'provenance': provenance,
    }


def build_text_evidence_fusion(
    ocr_regions: list[dict[str, Any]],
    vector_matches: list[dict[str, Any]],
    cad_matches: list[dict[str, Any]],
    *,
    review_threshold: float = 0.55,
    conflict_threshold: float = 0.35,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    vector_by_ocr = _best_match_by_ocr(vector_matches)
    cad_by_ocr = _best_match_by_ocr(cad_matches)
    items: list[dict[str, Any]] = []
    for index, region in enumerate(ocr_regions):
        vector = vector_by_ocr.get(index)
        cad = cad_by_ocr.get(index)
        ocr_confidence = _safe_float(region.get('confidence'))
        vector_score = _safe_float(vector.get('match_score')) if vector else 0.0
        cad_score = _safe_float(cad.get('match_score')) if cad else 0.0
        coverage = sum(1 for value in [ocr_confidence, vector_score, cad_score] if value > 0) / 3.0
        conflict = _text_conflict(region, vector, cad)
        confidence = _clamp((0.45 * ocr_confidence) + (0.30 * vector_score) + (0.20 * cad_score) + (0.05 * coverage) - (0.25 * conflict))
        review_required = confidence < review_threshold or conflict >= conflict_threshold
        items.append({
            'target_id': f'ocr:{index}',
            'text': region.get('text'),
            'source_pdf': region.get('source_pdf'),
            'page_index': region.get('page_index'),
            'page_contract_id': region.get('page_contract_id'),
            'pdf_bbox': region.get('pdf_bbox'),
            'confidence': round(confidence, 6),
            'review_required': review_required,
            'conflict_score': round(conflict, 6),
            'coverage_score': round(coverage, 6),
            'signals': {
                'ocr_confidence': ocr_confidence,
                'ocr_text': region.get('text'),
                'vector_match_score': vector_score,
                'vector_text': vector.get('vector_text') if vector else None,
                'vector_match_ref': _match_ref(vector),
                'cad_match_score': cad_score,
                'cad_text': cad.get('cad_text') if cad else None,
                'cad_match_ref': _match_ref(cad),
            },
        })
    avg_confidence = round(sum(float(item['confidence']) for item in items) / len(items), 6) if items else 0.0
    review_required_count = sum(1 for item in items if item['review_required'])
    conflict_count = sum(1 for item in items if float(item.get('conflict_score') or 0.0) >= conflict_threshold)
    return {
        'backend': 'text_evidence_fusion',
        'source': 'OCR_TEXT_REGIONS+OCR_VECTOR_TEXT_MATCHES+OCR_CAD_TEXT_MATCHES',
        'policy': {
            'version': 'weighted_text_evidence_score_v1',
            'weights': {'ocr_confidence': 0.45, 'vector_match': 0.30, 'cad_match': 0.20, 'coverage': 0.05, 'conflict_penalty': 0.25},
            'review_threshold': review_threshold,
            'conflict_threshold': conflict_threshold,
        },
        'summary': {
            'item_count': len(items),
            'review_required_count': review_required_count,
            'conflict_count': conflict_count,
            'avg_confidence': avg_confidence,
        },
        'items': items,
        'warnings': [],
        'provenance': provenance or {},
    }


def _best_match_by_ocr(matches: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for match in matches:
        try:
            ocr_index = int(match.get('ocr_index'))
        except Exception:
            continue
        current = rows.get(ocr_index)
        if current is None or _safe_float(match.get('match_score')) > _safe_float(current.get('match_score')):
            rows[ocr_index] = match
    return rows


def _text_conflict(region: dict[str, Any], vector: dict[str, Any] | None, cad: dict[str, Any] | None) -> float:
    texts = [str(region.get('text') or '').strip()]
    if vector and vector.get('vector_text') is not None:
        texts.append(str(vector.get('vector_text') or '').strip())
    if cad and cad.get('cad_text') is not None:
        texts.append(str(cad.get('cad_text') or '').strip())
    normalized = [_normalize_text(value) for value in texts if _normalize_text(value)]
    if len(normalized) <= 1:
        return 0.0
    unique = set(normalized)
    if len(unique) == 1:
        return 0.0
    # Simple conflict: count pairwise disagreement ratio.
    pairs = 0
    disagreements = 0
    for i, left in enumerate(normalized):
        for right in normalized[i + 1:]:
            pairs += 1
            if left != right:
                disagreements += 1
    return disagreements / pairs if pairs else 0.0


def _normalize_text(value: str) -> str:
    return ''.join(str(value or '').split()).lower()


def _match_ref(match: dict[str, Any] | None) -> dict[str, Any] | None:
    if not match:
        return None
    return {
        'match_score': match.get('match_score'),
        'bbox_iou': match.get('bbox_iou'),
        'text_similarity': match.get('text_similarity'),
    }


def _safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _markdown(report: dict[str, Any]) -> str:
    summary = report.get('summary') or {}
    policy = report.get('policy') or {}
    lines = [
        '# Text Evidence Fusion Report',
        '',
        f"- Backend: `{report.get('backend')}`",
        f"- Policy: `{policy.get('version')}`",
        f"- Item count: `{summary.get('item_count')}`",
        f"- Review required count: `{summary.get('review_required_count')}`",
        f"- Conflict count: `{summary.get('conflict_count')}`",
        f"- Average confidence: `{summary.get('avg_confidence')}`",
        '',
    ]
    return '\n'.join(lines)
