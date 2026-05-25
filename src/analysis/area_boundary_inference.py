from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def infer_area_boundaries(workspace: str | Path) -> dict[str, Any]:
    """Infer area/room boundary candidates from fileized CAD entities.

    This scaffold intentionally favors explainable candidate generation over final truth.
    Future implementation should add Shapely polygonize_full, snap tolerance, arc support, hatch support,
    raster contour cross-validation, and layer-aware filtering.
    """
    base = Path(workspace)
    entities = _load_entities(base)
    closed_polys = []
    line_candidates = []
    hatch_candidates = []
    for ent in entities:
        et = ent.get('entity_type')
        if et in {'LWPOLYLINE', 'POLYLINE'} and bool(ent.get('closed')):
            closed_polys.append(_candidate(ent, 'closed_polyline_area', 0.70))
        elif et in {'LINE', 'ARC', 'CIRCLE'}:
            line_candidates.append(_candidate(ent, 'open_linework_boundary_fragment', 0.20))
        elif et == 'HATCH':
            hatch_candidates.append(_candidate(ent, 'hatch_boundary_area', 0.60))
    payload = {
        'backend': 'area_boundary_inference',
        'schema_version': '0.1',
        'summary': {
            'closed_polyline_count': len(closed_polys),
            'line_fragment_count': len(line_candidates),
            'hatch_count': len(hatch_candidates),
            'candidate_count': len(closed_polys) + len(hatch_candidates),
        },
        'candidates': closed_polys + hatch_candidates,
        'fragments': line_candidates,
        'todo': [
            'Implement Shapely polygonize_full on LINE/ARC-derived segments.',
            'Add snap tolerance and gap closing report.',
            'Add hatch boundary extraction from ezdxf payload.',
            'Cross-check with RASTER_CONTOURS / RASTER_CONTOUR_CLASSES.',
            'Add layer-aware area filters after real webhard corpus calibration.',
        ],
        'warnings': ['scaffold only; not final room/area truth'],
    }
    (base / 'AREA_BOUNDARY_INFERENCE.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    (base / 'AREA_BOUNDARY_INFERENCE.md').write_text(_markdown(payload), encoding='utf-8')
    return payload


def _candidate(ent: dict[str, Any], signal: str, confidence: float) -> dict[str, Any]:
    return {
        'entity_id': ent.get('id'),
        'entity_type': ent.get('entity_type'),
        'layer': ent.get('layer'),
        'signal': signal,
        'confidence': confidence,
        'bbox': ent.get('bbox'),
        'area': ent.get('area'),
        'raw_ref': {'handle': ent.get('handle')},
    }


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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _markdown(payload: dict[str, Any]) -> str:
    summary = payload.get('summary') or {}
    lines = [
        '# Area Boundary Inference',
        '',
        f"- Closed polyline count: `{summary.get('closed_polyline_count')}`",
        f"- Line fragment count: `{summary.get('line_fragment_count')}`",
        f"- Hatch count: `{summary.get('hatch_count')}`",
        f"- Candidate count: `{summary.get('candidate_count')}`",
        '',
        '## TODO',
        '',
    ]
    for item in payload.get('todo') or []:
        lines.append(f'- {item}')
    lines.append('')
    return '\n'.join(lines)
