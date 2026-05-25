from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.workers.provenance import build_provenance


def write_text_review_queue(workspace: str | Path, *, include_all: bool = False) -> dict[str, Any]:
    base = Path(workspace)
    fusion_path = base / 'TEXT_EVIDENCE_FUSION.json'
    fusion_payload = _read_json(fusion_path)
    items = fusion_payload.get('items') or []
    provenance = build_provenance(
        workspace=base,
        backend='text_review_queue',
        algorithm='review_required_text_items_v1',
        source_artifacts=[str(fusion_path)],
        worker_name='text_review_queue',
    )
    queue = build_text_review_queue(items, include_all=include_all, provenance=provenance)
    out_json = base / 'TEXT_REVIEW_QUEUE.json'
    out_md = base / 'TEXT_REVIEW_QUEUE.md'
    out_json.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding='utf-8')
    out_md.write_text(_markdown(queue), encoding='utf-8')
    return {
        'backend': 'text_review_queue',
        'status': 'ok' if queue['summary']['queue_count'] else 'warning',
        'workspace': str(base),
        'source_item_count': len(items),
        'queue_count': queue['summary']['queue_count'],
        'high_conflict_count': queue['summary']['high_conflict_count'],
        'low_confidence_count': queue['summary']['low_confidence_count'],
        'artifacts': [str(out_json), str(out_md)],
        'warnings': queue.get('warnings') or [],
        'provenance': provenance,
    }


def build_text_review_queue(items: list[dict[str, Any]], *, include_all: bool = False, provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    queue_items: list[dict[str, Any]] = []
    for item in items:
        review_required = bool(item.get('review_required'))
        if not include_all and not review_required:
            continue
        confidence = _safe_float(item.get('confidence'))
        conflict_score = _safe_float(item.get('conflict_score'))
        reasons = _review_reasons(item)
        queue_items.append({
            'rank_key': {'conflict_score': conflict_score, 'confidence': confidence},
            'target_id': item.get('target_id'),
            'text': item.get('text'),
            'source_pdf': item.get('source_pdf'),
            'page_index': item.get('page_index'),
            'page_contract_id': item.get('page_contract_id'),
            'pdf_bbox': item.get('pdf_bbox'),
            'confidence': confidence,
            'conflict_score': conflict_score,
            'coverage_score': _safe_float(item.get('coverage_score')),
            'review_required': review_required,
            'review_reasons': reasons,
            'signals': item.get('signals') or {},
        })
    queue_items.sort(key=lambda row: (-_safe_float((row.get('rank_key') or {}).get('conflict_score')), _safe_float((row.get('rank_key') or {}).get('confidence'))))
    for index, row in enumerate(queue_items, start=1):
        row['review_rank'] = index
    high_conflict_count = sum(1 for item in queue_items if _safe_float(item.get('conflict_score')) >= 0.35)
    low_confidence_count = sum(1 for item in queue_items if _safe_float(item.get('confidence')) < 0.55)
    return {
        'backend': 'text_review_queue',
        'source': 'TEXT_EVIDENCE_FUSION',
        'summary': {
            'source_item_count': len(items),
            'queue_count': len(queue_items),
            'high_conflict_count': high_conflict_count,
            'low_confidence_count': low_confidence_count,
        },
        'items': queue_items,
        'warnings': [],
        'provenance': provenance or {},
    }


def _review_reasons(item: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    confidence = _safe_float(item.get('confidence'))
    conflict_score = _safe_float(item.get('conflict_score'))
    coverage_score = _safe_float(item.get('coverage_score'))
    if confidence < 0.55:
        reasons.append('low_confidence')
    if conflict_score >= 0.35:
        reasons.append('text_conflict')
    if coverage_score < 0.67:
        reasons.append('low_evidence_coverage')
    if bool(item.get('review_required')) and not reasons:
        reasons.append('review_required')
    return reasons


def _safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _markdown(queue: dict[str, Any]) -> str:
    summary = queue.get('summary') or {}
    lines = [
        '# Text Review Queue',
        '',
        f"- Source item count: `{summary.get('source_item_count')}`",
        f"- Queue count: `{summary.get('queue_count')}`",
        f"- High conflict count: `{summary.get('high_conflict_count')}`",
        f"- Low confidence count: `{summary.get('low_confidence_count')}`",
        '',
        '| Rank | Text | Confidence | Conflict | Reasons | Source |',
        '|---:|---|---:|---:|---|---|',
    ]
    for item in queue.get('items') or []:
        reasons = ', '.join(item.get('review_reasons') or [])
        source = f"{item.get('source_pdf') or ''} p{item.get('page_index')}"
        lines.append(f"| {item.get('review_rank')} | {item.get('text') or ''} | {item.get('confidence')} | {item.get('conflict_score')} | {reasons} | {source} |")
    if not queue.get('items'):
        lines.append('| - | No review items | - | - | - | - |')
    lines.append('')
    return '\n'.join(lines)
