from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from src.workers.provenance import build_provenance


ALLOWED_STATUS = {'pending', 'accepted', 'corrected', 'rejected', 'unclear'}


def write_text_corrections_apply(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    fusion_path = base / 'TEXT_EVIDENCE_FUSION.json'
    fusion_payload = _read_json(fusion_path)
    corrections = load_text_corrections(base)
    provenance = build_provenance(
        workspace=base,
        backend='text_corrections_apply',
        algorithm='human_correction_overlay_v1',
        source_artifacts=[str(fusion_path), str(base / 'TEXT_CORRECTIONS_TEMPLATE.json'), str(base / 'TEXT_CORRECTIONS_TEMPLATE.csv')],
        worker_name='text_corrections_apply',
    )
    applied = apply_text_corrections(fusion_payload, corrections, provenance=provenance)
    out_applied = base / 'TEXT_CORRECTIONS_APPLIED.json'
    out_corrected = base / 'TEXT_EVIDENCE_FUSION_CORRECTED.json'
    report = base / 'TEXT_CORRECTIONS_APPLY_REPORT.md'
    out_applied.write_text(json.dumps(applied['applied'], ensure_ascii=False, indent=2), encoding='utf-8')
    out_corrected.write_text(json.dumps(applied['corrected_fusion'], ensure_ascii=False, indent=2), encoding='utf-8')
    result = {
        'backend': 'text_corrections_apply',
        'status': 'ok' if applied['summary']['applied_count'] else 'warning',
        'workspace': str(base),
        'correction_count': applied['summary']['correction_count'],
        'applied_count': applied['summary']['applied_count'],
        'corrected_count': applied['summary']['corrected_count'],
        'accepted_count': applied['summary']['accepted_count'],
        'rejected_count': applied['summary']['rejected_count'],
        'artifacts': [str(out_applied), str(out_corrected), str(report)],
        'warnings': applied.get('warnings') or [],
        'provenance': provenance,
    }
    report.write_text(_markdown(result), encoding='utf-8')
    return result


def load_text_corrections(workspace: str | Path) -> list[dict[str, Any]]:
    base = Path(workspace)
    json_path = base / 'TEXT_CORRECTIONS.json'
    template_json = base / 'TEXT_CORRECTIONS_TEMPLATE.json'
    csv_path = base / 'TEXT_CORRECTIONS.csv'
    template_csv = base / 'TEXT_CORRECTIONS_TEMPLATE.csv'
    if json_path.exists():
        return _load_json_corrections(json_path)
    if template_json.exists():
        return _load_json_corrections(template_json)
    if csv_path.exists():
        return _load_csv_corrections(csv_path)
    if template_csv.exists():
        return _load_csv_corrections(template_csv)
    return []


def apply_text_corrections(fusion_payload: dict[str, Any], corrections: list[dict[str, Any]], *, provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    items = [dict(item) for item in fusion_payload.get('items') or []]
    by_target = {str(item.get('target_id')): item for item in items if item.get('target_id') is not None}
    applied_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for correction in corrections:
        target_id = str(correction.get('target_id') or '')
        if not target_id:
            continue
        status = _normalize_status(correction.get('correction_status'))
        if status == 'pending':
            continue
        item = by_target.get(target_id)
        if item is None:
            warnings.append(f'correction target not found: {target_id}')
            continue
        before_text = item.get('text')
        final_text = before_text
        usable = True
        human_verified = False
        if status == 'accepted':
            final_text = before_text
            usable = True
            human_verified = True
        elif status == 'corrected':
            corrected_text = str(correction.get('corrected_text') or '').strip()
            if not corrected_text:
                warnings.append(f'corrected status without corrected_text: {target_id}')
                continue
            final_text = corrected_text
            usable = True
            human_verified = True
        elif status == 'rejected':
            usable = False
            human_verified = True
        elif status == 'unclear':
            usable = False
            human_verified = False
        item['final_text'] = final_text
        item['usable'] = usable
        item['human_verified'] = human_verified
        item['correction_status'] = status
        item['correction_note'] = correction.get('reviewer_note') or ''
        item['correction_applied'] = True
        applied_rows.append({
            'target_id': target_id,
            'before_text': before_text,
            'final_text': final_text,
            'correction_status': status,
            'usable': usable,
            'human_verified': human_verified,
            'reviewer_note': correction.get('reviewer_note') or '',
        })
    for item in items:
        item.setdefault('final_text', item.get('text'))
        item.setdefault('usable', True)
        item.setdefault('human_verified', False)
        item.setdefault('correction_applied', False)
    summary = {
        'source_item_count': len(items),
        'correction_count': len(corrections),
        'applied_count': len(applied_rows),
        'accepted_count': sum(1 for row in applied_rows if row['correction_status'] == 'accepted'),
        'corrected_count': sum(1 for row in applied_rows if row['correction_status'] == 'corrected'),
        'rejected_count': sum(1 for row in applied_rows if row['correction_status'] == 'rejected'),
        'unclear_count': sum(1 for row in applied_rows if row['correction_status'] == 'unclear'),
    }
    corrected_fusion = dict(fusion_payload)
    corrected_fusion['items'] = items
    corrected_fusion['correction_overlay'] = {
        'backend': 'text_corrections_apply',
        'summary': summary,
        'provenance': provenance or {},
    }
    return {
        'applied': {
            'backend': 'text_corrections_apply',
            'summary': summary,
            'applied': applied_rows,
            'warnings': warnings,
            'provenance': provenance or {},
        },
        'corrected_fusion': corrected_fusion,
        'summary': summary,
        'warnings': warnings,
    }


def _load_json_corrections(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    if isinstance(payload.get('corrections'), list):
        return [row for row in payload.get('corrections') or [] if isinstance(row, dict)]
    if isinstance(payload.get('items'), list):
        return [row for row in payload.get('items') or [] if isinstance(row, dict)]
    return []


def _load_csv_corrections(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            rows.append(dict(row))
    return rows


def _normalize_status(value: Any) -> str:
    status = str(value or 'pending').strip().lower()
    return status if status in ALLOWED_STATUS else 'pending'


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _markdown(result: dict[str, Any]) -> str:
    lines = [
        '# Text Corrections Apply Report',
        '',
        f"- Backend: `{result.get('backend')}`",
        f"- Status: `{result.get('status')}`",
        f"- Correction count: `{result.get('correction_count')}`",
        f"- Applied count: `{result.get('applied_count')}`",
        f"- Accepted count: `{result.get('accepted_count')}`",
        f"- Corrected count: `{result.get('corrected_count')}`",
        f"- Rejected count: `{result.get('rejected_count')}`",
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
