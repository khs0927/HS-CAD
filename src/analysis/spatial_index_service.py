from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import bbox_center, bbox_iou, load_fileized_entities, read_json, write_json_and_md


def build_spatial_index(workspace: str | Path, *, bin_size: float = 1000.0) -> dict[str, Any]:
    """Build bbox-bin spatial index and candidate joins.

    This reduces O(n*m) scans by grouping bbox-bearing entities into grid bins.
    Shapely STRtree can be added later as an optional backend.
    """
    base = Path(workspace)
    entities = [e for e in load_fileized_entities(base) if _valid_bbox(e.get('bbox'))]
    bins: dict[str, list[str]] = {}
    entity_refs: dict[str, dict[str, Any]] = {}
    for ent in entities:
        ent_id = str(ent.get('id'))
        entity_refs[ent_id] = {
            'id': ent_id,
            'entity_type': ent.get('entity_type'),
            'layer': ent.get('layer'),
            'bbox': ent.get('bbox'),
            'file_id': ent.get('file_id'),
        }
        for key in _bins_for_bbox(ent.get('bbox'), bin_size):
            bins.setdefault(key, []).append(ent_id)
    text_area_candidates = _text_area_candidates(base, bins, entity_refs, bin_size)
    payload = {
        'backend': 'spatial_index_service',
        'schema_version': '0.1',
        'parameters': {'bin_size': bin_size},
        'summary': {
            'bbox_entity_count': len(entities),
            'bin_count': len(bins),
            'avg_entities_per_bin': round(sum(len(v) for v in bins.values()) / max(len(bins), 1), 6),
            'text_area_candidate_count': len(text_area_candidates),
        },
        'bins': [{'bin': k, 'count': len(v), 'entity_ids_sample': v[:20]} for k, v in sorted(bins.items())[:500]],
        'text_area_candidates': text_area_candidates[:5000],
        'todo': [
            'Add optional Shapely STRtree backend for exact geometry candidates.',
            'Add per-file/page partitioning before global binning.',
            'Use this index in leader/dimension/table graph builders.',
            'Persist compact index as parquet/duckdb for larger batches.',
        ],
        'warnings': ['bbox-bin scaffold; exact geometric predicates are not applied yet'],
    }
    return write_json_and_md(base, 'SPATIAL_INDEX_SERVICE', payload, _markdown(payload))


def _text_area_candidates(base: Path, bins: dict[str, list[str]], entity_refs: dict[str, dict[str, Any]], bin_size: float) -> list[dict[str, Any]]:
    text_roles = read_json(base / 'TEXT_ROLE_INFERENCE.json')
    area_payload = read_json(base / 'REAL_GEOMETRY_POLYGONIZER.json') or read_json(base / 'AREA_BOUNDARY_INFERENCE.json')
    texts = [item for item in text_roles.get('items') or [] if _valid_bbox(item.get('bbox'))]
    areas = []
    for poly in area_payload.get('polygons') or area_payload.get('candidates') or []:
        if _valid_bbox(poly.get('bbox')):
            areas.append(poly)
    candidates = []
    for text in texts:
        tbins = _bins_for_bbox(text.get('bbox'), bin_size)
        seen: set[str] = set()
        for area in areas:
            aid = str(area.get('polygon_id') or area.get('entity_id') or area.get('id') or '')
            if not aid or aid in seen:
                continue
            if not set(tbins).intersection(set(_bins_for_bbox(area.get('bbox'), bin_size))):
                continue
            iou = bbox_iou(text.get('bbox'), area.get('bbox'))
            tc = bbox_center(text.get('bbox'))
            ac = bbox_center(area.get('bbox'))
            dist = _dist(tc, ac)
            candidates.append({
                'text_id': text.get('target_id'),
                'area_id': aid,
                'text': text.get('text'),
                'text_role': text.get('role'),
                'bbox_iou': round(iou, 6),
                'center_distance': round(dist, 6) if dist is not None else None,
                'candidate_score': round((0.4 * iou) + (0.6 / (1.0 + (dist or 999999.0) / 1000.0)), 6),
            })
            seen.add(aid)
    candidates.sort(key=lambda row: float(row.get('candidate_score') or 0), reverse=True)
    return candidates


def _valid_bbox(bbox: Any) -> bool:
    return isinstance(bbox, list) and len(bbox) == 4


def _bins_for_bbox(bbox: Any, bin_size: float) -> list[str]:
    if not _valid_bbox(bbox):
        return []
    try:
        x1, y1, x2, y2 = [float(v) for v in bbox]
    except Exception:
        return []
    if bin_size <= 0:
        bin_size = 1000.0
    ix1, ix2 = math.floor(min(x1, x2) / bin_size), math.floor(max(x1, x2) / bin_size)
    iy1, iy2 = math.floor(min(y1, y2) / bin_size), math.floor(max(y1, y2) / bin_size)
    keys = []
    for ix in range(ix1, ix2 + 1):
        for iy in range(iy1, iy2 + 1):
            keys.append(f'{ix}:{iy}')
    return keys


def _dist(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float | None:
    if a is None or b is None:
        return None
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    return '\n'.join([
        '# Spatial Index Service',
        '',
        f"- BBox entity count: `{s.get('bbox_entity_count')}`",
        f"- Bin count: `{s.get('bin_count')}`",
        f"- Avg entities per bin: `{s.get('avg_entities_per_bin')}`",
        f"- Text-area candidates: `{s.get('text_area_candidate_count')}`",
        '',
    ])
