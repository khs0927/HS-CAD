from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.entity_loader import read_json, write_json_and_md

TITLE_KEYS = [
    '도면명', '도면번호', '축척', '일자', '작성', '검토', '승인', '공사명', '설계',
    'sheet', 'scale', 'date', 'drawn', 'checked', 'approved', 'project', 'title',
]


def classify_titleblocks(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    grid_payload = read_json(base / 'TABLE_GRID_DETECTOR.json')
    table_payload = read_json(base / 'TABLE_REGION_INFERENCE.json')
    text_roles = read_json(base / 'TEXT_ROLE_INFERENCE.json')
    key_hits = _title_key_hits(text_roles.get('items') or [])
    candidates = []

    for idx, cand in enumerate(grid_payload.get('candidates') or []):
        candidates.append({
            'titleblock_id': f'grid:{idx}',
            'source': 'TABLE_GRID_DETECTOR',
            'source_candidate': cand,
            'key_hit_count': len(key_hits),
            'confidence': _score_candidate(cand, key_hits, source='TABLE_GRID_DETECTOR'),
            'reason': 'grid_candidate_plus_title_key_hints',
        })

    for idx, cand in enumerate(table_payload.get('candidates') or []):
        candidates.append({
            'titleblock_id': f'table:{idx}',
            'source': 'TABLE_REGION_INFERENCE',
            'source_candidate': cand,
            'key_hit_count': len(key_hits),
            'confidence': _score_candidate(cand, key_hits, source='TABLE_REGION_INFERENCE'),
            'reason': 'table_candidate_plus_title_key_hints',
        })

    candidates.sort(key=lambda row: float(row.get('confidence') or 0), reverse=True)
    payload = {
        'backend': 'titleblock_classifier',
        'schema_version': '0.1',
        'summary': {
            'candidate_count': len(candidates),
            'key_hit_count': len(key_hits),
            'top_confidence': candidates[0]['confidence'] if candidates else 0.0,
        },
        'candidates': candidates,
        'key_hits': key_hits[:50],
        'todo': [
            'Add sheet boundary and lower-right page priors.',
            'Extract key-value pairs from detected titleblock cells.',
            'Add company/project template calibration after webhard sampling.',
            'Fuse with PDF vector text and OCR titleblock text roles.',
            'Add normalized drawing title, drawing id, scale, and date fields.',
        ],
        'warnings': ['scaffold only; titleblock classification requires page extent and template calibration'],
    }
    return write_json_and_md(base, 'TITLEBLOCK_CLASSIFIER', payload, _markdown(payload))


def _title_key_hits(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for item in items:
        text = str(item.get('text') or '').strip()
        normalized = text.lower().replace(' ', '')
        if item.get('role') == 'titleblock_text' or any(key.lower().replace(' ', '') in normalized for key in TITLE_KEYS):
            hits.append({
                'target_id': item.get('target_id'),
                'text': text,
                'role': item.get('role'),
                'confidence': item.get('confidence'),
                'bbox': item.get('bbox'),
            })
    return hits


def _score_candidate(candidate: dict[str, Any], key_hits: list[dict[str, Any]], *, source: str) -> float:
    base = 0.30 if source == 'TABLE_GRID_DETECTOR' else 0.25
    density_bonus = min(0.25, 0.01 * float(candidate.get('line_count') or candidate.get('inside_text_count') or 0))
    key_bonus = min(0.35, 0.03 * len(key_hits))
    return round(min(0.95, base + density_bonus + key_bonus), 6)


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    lines = [
        '# Titleblock Classifier',
        '',
        f"- Candidates: `{s.get('candidate_count')}`",
        f"- Key hits: `{s.get('key_hit_count')}`",
        f"- Top confidence: `{s.get('top_confidence')}`",
        '',
        '## TODO',
        '',
    ]
    for item in payload.get('todo') or []:
        lines.append(f'- {item}')
    lines.append('')
    return '\n'.join(lines)
