from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.entity_loader import bbox_center, load_fileized_entities, write_json_and_md

LINE_TYPES = {'LINE', 'LWPOLYLINE', 'POLYLINE'}
TEXT_TYPES = {'TEXT', 'MTEXT'}


def detect_table_grids(workspace: str | Path, *, angle_tolerance: float = 5.0) -> dict[str, Any]:
    """Detect table/grid candidates from vector linework.

    Scaffold strategy:
    - collect candidate horizontal/vertical linework by bbox aspect
    - group by file/layer
    - promote groups with both horizontal and vertical lines
    """
    base = Path(workspace)
    entities = load_fileized_entities(base)
    lines = [e for e in entities if e.get('entity_type') in LINE_TYPES]
    texts = [e for e in entities if e.get('entity_type') in TEXT_TYPES]
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for line in lines:
        orientation = _orientation_from_bbox(line.get('bbox'))
        if orientation == 'unknown':
            continue
        key = (str(line.get('file_id') or ''), str(line.get('layer') or ''))
        group = groups.setdefault(key, {'file_id': key[0], 'layer': key[1], 'horizontal': [], 'vertical': [], 'unknown': []})
        group[orientation].append(line.get('id'))
    candidates = []
    for key, group in groups.items():
        h = len(group.get('horizontal') or [])
        v = len(group.get('vertical') or [])
        if h >= 2 and v >= 2:
            candidates.append({
                'grid_id': f'{key[0]}:{key[1]}:{len(candidates)}',
                'file_id': key[0],
                'layer': key[1],
                'horizontal_count': h,
                'vertical_count': v,
                'line_count': h + v,
                'near_text_count': _rough_text_count(texts, key[0]),
                'confidence': round(min(0.85, 0.25 + 0.02 * (h + v)), 6),
                'reason': 'layer_has_multiple_horizontal_and_vertical_lines',
            })
    payload = {
        'backend': 'table_grid_detector',
        'schema_version': '0.1',
        'parameters': {'angle_tolerance': angle_tolerance},
        'summary': {
            'line_count': len(lines),
            'text_count': len(texts),
            'candidate_count': len(candidates),
        },
        'candidates': candidates,
        'todo': [
            'Replace bbox aspect orientation with actual line angle extraction.',
            'Compute grid intersections and cell rectangles.',
            'Fuse with pdfplumber table/line/rect objects.',
            'Fuse with OCR/text role table_text evidence.',
            'Classify schedule tables vs titleblocks vs detail notes.',
        ],
        'warnings': ['scaffold only; layer-level grouping can over-detect tables'],
    }
    return write_json_and_md(base, 'TABLE_GRID_DETECTOR', payload, _markdown(payload))


def _orientation_from_bbox(bbox: Any) -> str:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return 'unknown'
    try:
        x1, y1, x2, y2 = [float(v) for v in bbox]
    except Exception:
        return 'unknown'
    w, h = abs(x2 - x1), abs(y2 - y1)
    if w <= 0 and h <= 0:
        return 'unknown'
    if w >= h * 5:
        return 'horizontal'
    if h >= w * 5:
        return 'vertical'
    return 'unknown'


def _rough_text_count(texts: list[dict[str, Any]], file_id: str) -> int:
    return sum(1 for t in texts if str(t.get('file_id') or '') == file_id)


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    return '\n'.join([
        '# Table Grid Detector',
        '',
        f"- Lines: `{s.get('line_count')}`",
        f"- Texts: `{s.get('text_count')}`",
        f"- Candidates: `{s.get('candidate_count')}`",
        '',
    ])
