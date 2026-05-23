from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import bbox_center, distance, load_fileized_entities, write_json_and_md

TEXT_TYPES = {'TEXT', 'MTEXT'}
DIM_TYPES = {'DIMENSION', 'ALIGNED_DIMENSION', 'ROTATED_DIMENSION', 'LINEAR_DIMENSION'}
LINE_TYPES = {'LINE', 'LWPOLYLINE', 'POLYLINE'}
NUMERIC_RE = re.compile(r'^[~≈]?[0-9]+([,.][0-9]+)?(\s*(mm|m|cm))?$', re.IGNORECASE)


def build_dimension_graph(workspace: str | Path, *, max_distance: float = 800.0) -> dict[str, Any]:
    base = Path(workspace)
    entities = load_fileized_entities(base)
    dimensions = [e for e in entities if e.get('entity_type') in DIM_TYPES]
    numeric_texts = [e for e in entities if e.get('entity_type') in TEXT_TYPES and _looks_dimension_text(e.get('text') or e.get('value') or e.get('content'))]
    lines = [e for e in entities if e.get('entity_type') in LINE_TYPES]
    nodes = []
    edges = []
    for dim in dimensions:
        nodes.append(_node(dim, 'dimension_entity'))
    for txt in numeric_texts:
        nodes.append(_node(txt, 'dimension_text_candidate'))
    for line in lines:
        nodes.append(_node(line, 'dimension_line_candidate'))
    for txt in numeric_texts:
        tc = bbox_center(txt.get('bbox'))
        nearest = []
        for line in lines:
            dist = distance(tc, bbox_center(line.get('bbox')))
            if dist is not None and dist <= max_distance:
                nearest.append((dist, line))
        nearest.sort(key=lambda pair: pair[0])
        for dist, line in nearest[:4]:
            edges.append({
                'from': txt.get('id'),
                'to': line.get('id'),
                'edge_type': 'numeric_text_near_dimension_line_candidate',
                'distance': round(dist, 6),
                'confidence': round(max(0.05, 1.0 - dist / max_distance) * 0.40, 6),
            })
    payload = {
        'backend': 'dimension_graph_builder',
        'schema_version': '0.1',
        'parameters': {'max_distance': max_distance},
        'summary': {
            'dimension_entity_count': len(dimensions),
            'numeric_text_count': len(numeric_texts),
            'line_candidate_count': len(lines),
            'edge_count': len(edges),
        },
        'nodes': nodes,
        'edges': edges,
        'todo': [
            'Detect arrowheads/ticks and extension lines.',
            'Group dimension chains by collinearity and offset.',
            'Infer unit context from drawing scale/title block.',
            'Distinguish true dimensions from room names like A101.',
            'Add geometric projection from text to dimension line.',
        ],
        'warnings': ['scaffold only; numeric text can include non-dimension labels'],
    }
    return write_json_and_md(base, 'DIMENSION_GRAPH', payload, _markdown(payload))


def _looks_dimension_text(value: Any) -> bool:
    s = str(value or '').strip().replace(',', '')
    if not s or len(s) > 16:
        return False
    if NUMERIC_RE.match(s):
        return True
    return any(ch.isdigit() for ch in s) and any(token in s.lower() for token in ['ø', 'r', 'x', '×'])


def _node(ent: dict[str, Any], role: str) -> dict[str, Any]:
    return {
        'id': ent.get('id'),
        'role': role,
        'entity_type': ent.get('entity_type'),
        'layer': ent.get('layer'),
        'text': ent.get('text') or ent.get('value') or ent.get('content'),
        'bbox': ent.get('bbox'),
    }


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    return '\n'.join([
        '# Dimension Graph',
        '',
        f"- Dimension entities: `{s.get('dimension_entity_count')}`",
        f"- Numeric texts: `{s.get('numeric_text_count')}`",
        f"- Line candidates: `{s.get('line_candidate_count')}`",
        f"- Edges: `{s.get('edge_count')}`",
        '',
    ])
