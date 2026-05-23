from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROLE_LABELS = [
    'room_name',
    'dimension_text',
    'leader_note',
    'table_text',
    'titleblock_text',
    'material_note',
    'drawing_note',
    'sheet_index',
    'unknown',
]

MATERIAL_HINTS = ['t', 'thk', '판넬', '글라스울', '석고', '콘크리트', '철골', 'h-', 'h빔', '마감', '몰탈', '단열']
DIMENSION_HINT_RE = re.compile(r'^(\d+[,.]?\d*|\d+[xX×]\d+|[øØ]\s*\d+|R\s*\d+)$')
ROOM_HINTS = ['실', '실명', '사무', '창고', '화장실', '복도', '기계실', '전기실', '탕비', '회의', '홀']
TITLE_HINTS = ['도면명', '축척', '일자', '설계', '검토', '승인', '도면번호', 'sheet', 'scale', 'date']
LEADER_HINTS = ['참조', '확인', '설치', '철거', '신설', '기존', '상세', '주의', '확대']


def infer_text_roles(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    text_items = _load_text_items(base)
    rows = [classify_text_item(item) for item in text_items]
    summary: dict[str, int] = {label: 0 for label in ROLE_LABELS}
    for row in rows:
        summary[row['role']] = summary.get(row['role'], 0) + 1
    payload = {
        'backend': 'text_role_inference',
        'schema_version': '0.1',
        'summary': {'text_count': len(rows), 'role_counts': summary},
        'items': rows,
        'warnings': ['scaffold heuristic only; requires real drawing calibration'],
    }
    (base / 'TEXT_ROLE_INFERENCE.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    (base / 'TEXT_ROLE_INFERENCE.md').write_text(_markdown(payload), encoding='utf-8')
    return payload


def classify_text_item(item: dict[str, Any]) -> dict[str, Any]:
    text = str(item.get('text') or '').strip()
    normalized = ''.join(text.lower().split())
    scores = {label: 0.0 for label in ROLE_LABELS}
    if not text:
        scores['unknown'] += 1.0
    if DIMENSION_HINT_RE.match(normalized):
        scores['dimension_text'] += 0.85
    if any(hint in normalized for hint in MATERIAL_HINTS):
        scores['material_note'] += 0.65
    if any(hint in normalized for hint in TITLE_HINTS):
        scores['titleblock_text'] += 0.60
    if any(hint in normalized for hint in LEADER_HINTS):
        scores['leader_note'] += 0.45
    if any(hint in normalized for hint in ROOM_HINTS) and len(normalized) <= 16:
        scores['room_name'] += 0.55
    if item.get('source') == 'pdf_vector' and _looks_like_table_cell(item):
        scores['table_text'] += 0.50
    if len(text) > 20 and scores['material_note'] < 0.5:
        scores['drawing_note'] += 0.35
    if all(value == 0.0 for value in scores.values()):
        scores['unknown'] = 0.35
    role = max(scores.items(), key=lambda pair: pair[1])[0]
    confidence = round(max(scores.values()), 6)
    return {
        'target_id': item.get('target_id'),
        'text': text,
        'role': role,
        'confidence': confidence,
        'scores': scores,
        'source': item.get('source'),
        'source_ref': item.get('source_ref'),
        'bbox': item.get('bbox'),
        'layer': item.get('layer'),
    }


def _load_text_items(base: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fusion = _read_json(base / 'TEXT_EVIDENCE_FUSION_CORRECTED.json') or _read_json(base / 'TEXT_EVIDENCE_FUSION.json')
    for item in fusion.get('items') or []:
        rows.append({
            'target_id': item.get('target_id'),
            'text': item.get('final_text') or item.get('text'),
            'source': 'text_evidence_fusion',
            'source_ref': 'TEXT_EVIDENCE_FUSION',
            'bbox': item.get('pdf_bbox'),
        })
    cad_dir = base / 'fileized' / 'json'
    if cad_dir.exists():
        for path in sorted(cad_dir.glob('*.json')):
            payload = _read_json(path)
            for idx, ent in enumerate(payload.get('entities') or []):
                et = str(ent.get('entity_type') or ent.get('type') or '').upper()
                if et in {'TEXT', 'MTEXT'}:
                    rows.append({
                        'target_id': f'{payload.get("file_id") or path.stem}:{idx}',
                        'text': ent.get('text') or ent.get('value') or ent.get('content'),
                        'source': 'cad_text',
                        'source_ref': str(path),
                        'bbox': ent.get('bbox'),
                        'layer': ent.get('layer'),
                    })
    return rows


def _looks_like_table_cell(item: dict[str, Any]) -> bool:
    bbox = item.get('bbox') or []
    return isinstance(bbox, list) and len(bbox) == 4 and abs(float(bbox[3]) - float(bbox[1])) < 20


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _markdown(payload: dict[str, Any]) -> str:
    lines = ['# Text Role Inference', '', '| Role | Count |', '|---|---:|']
    for role, count in (payload.get('summary') or {}).get('role_counts', {}).items():
        lines.append(f'| {role} | {count} |')
    lines.append('')
    return '\n'.join(lines)
