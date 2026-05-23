from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def infer_leader_notes(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    entities = _load_entities(base)
    texts = [e for e in entities if e.get('entity_type') in {'TEXT', 'MTEXT'}]
    lines = [e for e in entities if e.get('entity_type') in {'LINE', 'LWPOLYLINE', 'POLYLINE'}]
    candidates = []
    for text in texts:
        nearest = _nearest_line_hint(text, lines)
        if nearest:
            candidates.append({
                'text_id': text.get('id'),
                'text': text.get('text'),
                'leader_candidate': nearest,
                'confidence': 0.35,
                'reason': 'nearest_line_or_polyline_scaffold',
            })
    return _write(base, 'LEADER_NOTE_INFERENCE', {'candidates': candidates, 'warnings': ['scaffold only']})


def infer_dimension_texts(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    entities = _load_entities(base)
    candidates = []
    for ent in entities:
        if ent.get('entity_type') in {'DIMENSION', 'ALIGNED_DIMENSION', 'ROTATED_DIMENSION'}:
            candidates.append({'entity': ent, 'role': 'dimension_entity', 'confidence': 0.9})
        elif ent.get('entity_type') in {'TEXT', 'MTEXT'} and _looks_numeric(ent.get('text')):
            candidates.append({'entity': ent, 'role': 'dimension_text_candidate', 'confidence': 0.55})
    return _write(base, 'DIMENSION_TEXT_INFERENCE', {'candidates': candidates, 'warnings': ['scaffold only']})


def infer_table_regions(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    entities = _load_entities(base)
    rect_like = [e for e in entities if e.get('entity_type') in {'LWPOLYLINE', 'POLYLINE'} and e.get('closed')]
    text_like = [e for e in entities if e.get('entity_type') in {'TEXT', 'MTEXT'}]
    candidates = []
    for region in rect_like:
        inside_count = _rough_inside_count(region, text_like)
        if inside_count >= 3:
            candidates.append({'region': region, 'inside_text_count': inside_count, 'confidence': min(0.85, 0.3 + inside_count * 0.05)})
    return _write(base, 'TABLE_REGION_INFERENCE', {'candidates': candidates, 'warnings': ['scaffold only']})


def infer_titleblocks(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    table_payload = _read_json(base / 'TABLE_REGION_INFERENCE.json')
    candidates = []
    for idx, region in enumerate(table_payload.get('candidates') or []):
        # Title blocks often sit near sheet boundary. This scaffold promotes dense tables as possible titleblocks.
        candidates.append({'table_index': idx, 'source': region, 'role': 'titleblock_candidate', 'confidence': 0.35})
    return _write(base, 'TITLEBLOCK_INFERENCE', {'candidates': candidates, 'warnings': ['scaffold only']})


def _load_entities(base: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    json_dir = base / 'fileized' / 'json'
    if not json_dir.exists():
        return rows
    for path in sorted(json_dir.glob('*.json')):
        payload = _read_json(path)
        for idx, ent in enumerate(payload.get('entities') or []):
            if not isinstance(ent, dict):
                continue
            row = dict(ent)
            row.setdefault('id', f'{payload.get("file_id") or path.stem}:{idx}')
            row['entity_type'] = str(row.get('entity_type') or row.get('type') or '').upper()
            rows.append(row)
    return rows


def _nearest_line_hint(text: dict[str, Any], lines: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not lines:
        return None
    return {'line_id': lines[0].get('id'), 'entity_type': lines[0].get('entity_type')}


def _looks_numeric(value: Any) -> bool:
    s = str(value or '').strip().replace(',', '')
    return bool(s) and any(ch.isdigit() for ch in s) and len(s) <= 16


def _rough_inside_count(region: dict[str, Any], texts: list[dict[str, Any]]) -> int:
    # TODO: replace with real bbox/geometry containment.
    return min(len(texts), 0)


def _write(base: Path, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = {'backend': name.lower(), 'schema_version': '0.1', **payload}
    (base / f'{name}.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (base / f'{name}.md').write_text(f'# {name}\n\n- Candidate count: `{len(payload.get("candidates") or [])}`\n', encoding='utf-8')
    return result


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
