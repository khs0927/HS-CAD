from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from src.workers.provenance import build_provenance


CSV_FIELDS = [
    'review_rank',
    'target_id',
    'text',
    'corrected_text',
    'correction_status',
    'reviewer_note',
    'confidence',
    'conflict_score',
    'coverage_score',
    'review_reasons',
    'source_pdf',
    'page_index',
    'page_contract_id',
]


def write_text_corrections_export(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    queue_path = base / 'TEXT_REVIEW_QUEUE.json'
    queue_payload = _read_json(queue_path)
    items = queue_payload.get('items') or []
    provenance = build_provenance(
        workspace=base,
        backend='text_corrections_export',
        algorithm='review_queue_csv_and_correction_template_v1',
        source_artifacts=[str(queue_path)],
        worker_name='text_corrections_export',
    )
    corrections = build_text_corrections_template(items, provenance=provenance)
    queue_csv = base / 'TEXT_REVIEW_QUEUE.csv'
    template_json = base / 'TEXT_CORRECTIONS_TEMPLATE.json'
    template_csv = base / 'TEXT_CORRECTIONS_TEMPLATE.csv'
    _write_csv(queue_csv, _rows_for_csv(items))
    template_json.write_text(json.dumps(corrections, ensure_ascii=False, indent=2), encoding='utf-8')
    _write_csv(template_csv, _rows_for_csv(corrections.get('corrections') or []))
    report_path = base / 'TEXT_CORRECTIONS_EXPORT_REPORT.md'
    result = {
        'backend': 'text_corrections_export',
        'status': 'ok' if items else 'warning',
        'workspace': str(base),
        'queue_count': len(items),
        'artifacts': [str(queue_csv), str(template_json), str(template_csv), str(report_path)],
        'warnings': [] if items else ['no review queue items found'],
        'provenance': provenance,
    }
    report_path.write_text(_markdown(result), encoding='utf-8')
    return result


def build_text_corrections_template(items: list[dict[str, Any]], *, provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for item in items:
        rows.append({
            'review_rank': item.get('review_rank'),
            'target_id': item.get('target_id'),
            'text': item.get('text'),
            'corrected_text': '',
            'correction_status': 'pending',
            'reviewer_note': '',
            'confidence': item.get('confidence'),
            'conflict_score': item.get('conflict_score'),
            'coverage_score': item.get('coverage_score'),
            'review_reasons': item.get('review_reasons') or [],
            'source_pdf': item.get('source_pdf'),
            'page_index': item.get('page_index'),
            'page_contract_id': item.get('page_contract_id'),
            'pdf_bbox': item.get('pdf_bbox'),
            'signals': item.get('signals') or {},
        })
    return {
        'backend': 'text_corrections_export',
        'schema_version': '1.0',
        'instructions': {
            'correction_status_allowed': ['pending', 'accepted', 'corrected', 'rejected', 'unclear'],
            'corrected_text': 'Fill only when correction_status is corrected.',
            'reviewer_note': 'Optional human note for future calibration.',
        },
        'summary': {
            'correction_count': len(rows),
            'pending_count': len(rows),
        },
        'corrections': rows,
        'provenance': provenance or {},
    }


def _rows_for_csv(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        rows.append({
            'review_rank': item.get('review_rank'),
            'target_id': item.get('target_id'),
            'text': item.get('text'),
            'corrected_text': item.get('corrected_text') or '',
            'correction_status': item.get('correction_status') or 'pending',
            'reviewer_note': item.get('reviewer_note') or '',
            'confidence': item.get('confidence'),
            'conflict_score': item.get('conflict_score'),
            'coverage_score': item.get('coverage_score'),
            'review_reasons': ';'.join(item.get('review_reasons') or []),
            'source_pdf': item.get('source_pdf'),
            'page_index': item.get('page_index'),
            'page_contract_id': item.get('page_contract_id'),
        })
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, '') for field in CSV_FIELDS})


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _markdown(result: dict[str, Any]) -> str:
    lines = [
        '# Text Corrections Export Report',
        '',
        f"- Backend: `{result.get('backend')}`",
        f"- Status: `{result.get('status')}`",
        f"- Queue count: `{result.get('queue_count')}`",
        '',
        '## Artifacts',
        '',
    ]
    for artifact in result.get('artifacts') or []:
        lines.append(f'- `{artifact}`')
    lines.extend(['', '## Warnings', ''])
    for warning in result.get('warnings') or []:
        lines.append(f'- {warning}')
    if not result.get('warnings'):
        lines.append('- None')
    lines.append('')
    return '\n'.join(lines)
