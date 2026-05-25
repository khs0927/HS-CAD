from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import read_json, write_json_and_md

KEY_PATTERNS = {
    'drawing_title': ['도면명', 'title', 'drawing title'],
    'drawing_number': ['도면번호', '도번', 'dwg no', 'drawing no', 'no.'],
    'scale': ['축척', 'scale'],
    'date': ['일자', '작성일', 'date'],
    'project_name': ['공사명', '프로젝트', 'project'],
    'drawn_by': ['작성', 'drawn'],
    'checked_by': ['검토', 'checked'],
    'approved_by': ['승인', 'approved'],
}


def extract_titleblock_key_values(workspace: str | Path) -> dict[str, Any]:
    """Extract titleblock key-value candidates.

    Scaffold strategy:
    - read TITLEBLOCK_CLASSIFIER key hits and TEXT_ROLE_INFERENCE items
    - detect key labels by text matching
    - assign following nearby/unstructured text as unresolved value candidate when possible
    """
    base = Path(workspace)
    title_payload = read_json(base / 'TITLEBLOCK_CLASSIFIER.json')
    text_roles = read_json(base / 'TEXT_ROLE_INFERENCE.json')
    text_items = text_roles.get('items') or []
    key_values = []
    for field, patterns in KEY_PATTERNS.items():
        hits = []
        for item in text_items:
            text = str(item.get('text') or '').strip()
            normalized = _norm(text)
            if any(_norm(pattern) in normalized for pattern in patterns):
                hits.append(item)
        if hits:
            for idx, hit in enumerate(hits[:10]):
                key_values.append({
                    'field': field,
                    'key_text': hit.get('text'),
                    'value_text': _extract_inline_value(str(hit.get('text') or '')),
                    'source_text_id': hit.get('target_id'),
                    'bbox': hit.get('bbox'),
                    'confidence': 0.45 if _extract_inline_value(str(hit.get('text') or '')) else 0.30,
                    'reason': 'titleblock_key_pattern_match_scaffold',
                })
        else:
            key_values.append({
                'field': field,
                'key_text': None,
                'value_text': None,
                'source_text_id': None,
                'bbox': None,
                'confidence': 0.0,
                'reason': 'not_found',
            })
    payload = {
        'backend': 'titleblock_key_value_extractor',
        'schema_version': '0.1',
        'summary': {
            'titleblock_candidate_count': len(title_payload.get('candidates') or []),
            'text_item_count': len(text_items),
            'key_value_candidate_count': len([kv for kv in key_values if kv.get('key_text')]),
        },
        'key_values': key_values,
        'normalized_sheet_metadata': _normalized_metadata(key_values),
        'todo': [
            'Use detected titleblock cell grid to pair key/value by neighboring cells.',
            'Use OCR/PDF/CAD corrected final_text rather than raw role text only.',
            'Normalize scale/date/drawing number formats.',
            'Add project/company template calibration.',
            'Emit DRAWING_SHEET_METADATA.json as stable downstream schema.',
        ],
        'warnings': ['scaffold only; key-value pairing is mostly pattern based'],
    }
    write_json_and_md(base, 'TITLEBLOCK_KEY_VALUES', payload, _markdown(payload))
    metadata = {
        'backend': 'drawing_sheet_metadata',
        'schema_version': '0.1',
        'metadata': payload['normalized_sheet_metadata'],
        'source': 'TITLEBLOCK_KEY_VALUES.json',
        'warnings': payload['warnings'],
    }
    write_json_and_md(base, 'DRAWING_SHEET_METADATA', metadata, '# Drawing Sheet Metadata\n')
    return payload


def _extract_inline_value(text: str) -> str | None:
    if ':' in text:
        value = text.split(':', 1)[1].strip()
        return value or None
    if '：' in text:
        value = text.split('：', 1)[1].strip()
        return value or None
    return None


def _normalized_metadata(key_values: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in key_values:
        field = row.get('field')
        if not field or field in out:
            continue
        value = row.get('value_text')
        if value:
            out[str(field)] = value
    return out


def _norm(value: str) -> str:
    return re.sub(r'\s+', '', value.lower())


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    lines = [
        '# Titleblock Key Values',
        '',
        f"- Titleblock candidates: `{s.get('titleblock_candidate_count')}`",
        f"- Text items: `{s.get('text_item_count')}`",
        f"- Key-value candidates: `{s.get('key_value_candidate_count')}`",
        '',
        '| Field | Key | Value | Confidence |',
        '|---|---|---|---:|',
    ]
    for row in payload.get('key_values') or []:
        lines.append(f"| {row.get('field')} | {row.get('key_text') or ''} | {row.get('value_text') or ''} | {row.get('confidence')} |")
    lines.append('')
    return '\n'.join(lines)
