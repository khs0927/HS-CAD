from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.entity_loader import bbox_center, distance, load_fileized_entities, write_json_and_md

BOUNDARY_TYPES = {'LINE', 'ARC', 'CIRCLE', 'LWPOLYLINE', 'POLYLINE', 'HATCH'}


def build_geometry_loops(workspace: str | Path, *, snap_tolerance: float = 50.0) -> dict[str, Any]:
    """Build explainable loop candidates from CAD entity fragments.

    This is a scaffold for practical drawings where boundaries are often exploded into LINE/ARC fragments.
    It does not yet perform true polygonization; it creates grouped candidates and TODO metadata.
    """
    base = Path(workspace)
    entities = [e for e in load_fileized_entities(base) if e.get('entity_type') in BOUNDARY_TYPES]
    closed = [_closed_candidate(e) for e in entities if e.get('entity_type') in {'LWPOLYLINE', 'POLYLINE'} and bool(e.get('closed'))]
    hatch = [_closed_candidate(e, signal='hatch_boundary') for e in entities if e.get('entity_type') == 'HATCH']
    fragments = [e for e in entities if e.get('entity_type') in {'LINE', 'ARC', 'CIRCLE'}]
    fragment_groups = _group_by_layer_and_proximity(fragments, snap_tolerance=snap_tolerance)
    payload = {
        'backend': 'geometry_loop_builder',
        'schema_version': '0.1',
        'parameters': {'snap_tolerance': snap_tolerance},
        'summary': {
            'boundary_entity_count': len(entities),
            'closed_polyline_candidate_count': len(closed),
            'hatch_candidate_count': len(hatch),
            'fragment_count': len(fragments),
            'fragment_group_count': len(fragment_groups),
        },
        'closed_candidates': closed + hatch,
        'fragment_groups': fragment_groups,
        'todo': [
            'Replace proximity grouping with endpoint graph and connected component extraction.',
            'Convert LINE/ARC/CIRCLE fragments to Shapely LineString approximations.',
            'Run shapely.polygonize_full and keep polygons/dangles/cut_edges/invalid_rings.',
            'Add snap tolerance sweep and gap-closing audit.',
            'Add layer-aware filters only after real webhard calibration.',
        ],
        'warnings': ['scaffold only; no final room/area truth yet'],
    }
    md = _markdown(payload)
    return write_json_and_md(base, 'GEOMETRY_LOOP_BUILDER', payload, md)


def _closed_candidate(ent: dict[str, Any], *, signal: str = 'closed_polyline') -> dict[str, Any]:
    return {
        'entity_id': ent.get('id'),
        'file_id': ent.get('file_id'),
        'entity_type': ent.get('entity_type'),
        'layer': ent.get('layer'),
        'bbox': ent.get('bbox'),
        'signal': signal,
        'confidence': 0.7 if signal == 'closed_polyline' else 0.6,
    }


def _group_by_layer_and_proximity(fragments: list[dict[str, Any]], *, snap_tolerance: float) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    by_layer: dict[str, list[dict[str, Any]]] = {}
    for ent in fragments:
        by_layer.setdefault(str(ent.get('layer') or ''), []).append(ent)
    for layer, ents in by_layer.items():
        used: set[str] = set()
        for ent in ents:
            ent_id = str(ent.get('id'))
            if ent_id in used:
                continue
            center = bbox_center(ent.get('bbox'))
            members = [ent]
            used.add(ent_id)
            for other in ents:
                oid = str(other.get('id'))
                if oid in used:
                    continue
                dist = distance(center, bbox_center(other.get('bbox')))
                if dist is not None and dist <= snap_tolerance * 10:
                    members.append(other)
                    used.add(oid)
            groups.append({
                'group_id': f'{layer}:{len(groups)}',
                'layer': layer,
                'member_count': len(members),
                'entity_ids': [m.get('id') for m in members],
                'confidence': min(0.45, 0.10 + 0.02 * len(members)),
                'reason': 'layer_and_bbox_center_proximity_scaffold',
            })
    return groups


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    return '\n'.join([
        '# Geometry Loop Builder',
        '',
        f"- Boundary entity count: `{s.get('boundary_entity_count')}`",
        f"- Closed polyline candidates: `{s.get('closed_polyline_candidate_count')}`",
        f"- Hatch candidates: `{s.get('hatch_candidate_count')}`",
        f"- Fragment count: `{s.get('fragment_count')}`",
        f"- Fragment groups: `{s.get('fragment_group_count')}`",
        '',
        '## TODO',
        '',
        *[f'- {item}' for item in payload.get('todo') or []],
        '',
    ])
