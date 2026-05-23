from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.entity_loader import bbox_center, distance, load_fileized_entities, write_json_and_md

TEXT_TYPES = {'TEXT', 'MTEXT'}
LINE_TYPES = {'LINE', 'LWPOLYLINE', 'POLYLINE'}
DEFAULT_MAX_TEXTS = 2000
DEFAULT_MAX_LINEWORK = 5000


def build_leader_graph(
    workspace: str | Path,
    *,
    max_distance: float = 500.0,
    max_texts: int = DEFAULT_MAX_TEXTS,
    max_linework: int = DEFAULT_MAX_LINEWORK,
) -> dict[str, Any]:
    base = Path(workspace)
    entities = load_fileized_entities(base)
    all_texts = [e for e in entities if e.get('entity_type') in TEXT_TYPES]
    all_linework = [e for e in entities if e.get('entity_type') in LINE_TYPES]
    texts = all_texts[:max_texts]
    linework = all_linework[:max_linework]
    nodes = []
    edges = []
    for text in texts:
        nodes.append(_node(text, 'text'))
    for line in linework:
        nodes.append(_node(line, 'leader_line_candidate'))
    for text in texts:
        tc = bbox_center(text.get('bbox'))
        candidates = []
        for line in linework:
            dist = distance(tc, bbox_center(line.get('bbox')))
            if dist is not None and dist <= max_distance:
                candidates.append((dist, line))
        candidates.sort(key=lambda pair: pair[0])
        for dist, line in candidates[:3]:
            edges.append({
                'from': text.get('id'),
                'to': line.get('id'),
                'edge_type': 'near_leader_candidate',
                'distance': round(dist, 6),
                'confidence': round(max(0.05, 1.0 - dist / max_distance) * 0.45, 6),
            })
    payload = {
        'backend': 'leader_graph_builder',
        'schema_version': '0.1',
        'parameters': {'max_distance': max_distance, 'max_texts': max_texts, 'max_linework': max_linework},
        'summary': {
            'text_node_count': len(all_texts),
            'line_candidate_count': len(all_linework),
            'sampled_text_node_count': len(texts),
            'sampled_line_candidate_count': len(linework),
            'edge_count': len(edges),
        },
        'nodes': nodes,
        'edges': edges,
        'todo': [
            'Use actual leader entity types when present.',
            'Trace polyline endpoints and arrowhead blocks.',
            'Prefer endpoint-to-text distance over bbox center distance.',
            'Add spatial index for large drawings.',
            'Fuse with TEXT_ROLE_INFERENCE leader_note scores.',
        ],
        'warnings': _warnings(len(all_texts), len(all_linework), len(texts), len(linework)),
    }
    return write_json_and_md(base, 'LEADER_GRAPH', payload, _markdown(payload))


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
        '# Leader Graph',
        '',
        f"- Text nodes: `{s.get('text_node_count')}`",
        f"- Line candidates: `{s.get('line_candidate_count')}`",
        f"- Sampled text nodes: `{s.get('sampled_text_node_count')}`",
        f"- Sampled line candidates: `{s.get('sampled_line_candidate_count')}`",
        f"- Edges: `{s.get('edge_count')}`",
        '',
    ])


def _warnings(total_texts: int, total_lines: int, sampled_texts: int, sampled_lines: int) -> list[str]:
    warnings = ['scaffold only; bbox center proximity may be noisy']
    if sampled_texts < total_texts or sampled_lines < total_lines:
        warnings.append('large workspace sampled to avoid O(text*line) scaffold timeout')
    return warnings
