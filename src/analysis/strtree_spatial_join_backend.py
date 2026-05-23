from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.entity_loader import bbox_center, load_fileized_entities, read_json, write_json_and_md

try:  # optional dependency
    from shapely.geometry import box, Point
    from shapely.strtree import STRtree
    SHAPELY_AVAILABLE = True
    SHAPELY_ERROR = None
except Exception as exc:  # pragma: no cover
    box = None  # type: ignore
    Point = None  # type: ignore
    STRtree = None  # type: ignore
    SHAPELY_AVAILABLE = False
    SHAPELY_ERROR = str(exc)

TEXT_TYPES = {'TEXT', 'MTEXT'}


def run_strtree_spatial_join(workspace: str | Path) -> dict[str, Any]:
    """Optional Shapely STRtree spatial join backend.

    Builds an STRtree over area polygon/candidate bboxes and queries text centers.
    Falls back to unavailable artifact when Shapely is not installed.
    """
    base = Path(workspace)
    if not SHAPELY_AVAILABLE:
        payload = {
            'backend': 'strtree_spatial_join_backend',
            'status': 'unavailable',
            'reason': SHAPELY_ERROR,
            'summary': {'area_count': 0, 'text_count': 0, 'join_count': 0},
            'joins': [],
            'warnings': ['Shapely is not installed; STRtree join skipped'],
        }
        return write_json_and_md(base, 'STRTREE_SPATIAL_JOIN', payload, _markdown(payload))

    area_payload = read_json(base / 'REAL_GEOMETRY_POLYGONIZER.json') or read_json(base / 'AREA_BOUNDARY_INFERENCE.json')
    text_roles = read_json(base / 'TEXT_ROLE_INFERENCE.json')
    areas = _area_records(area_payload)
    texts = _text_records(text_roles, base)
    geoms = []
    geom_to_area: dict[int, dict[str, Any]] = {}
    for area in areas:
        geom = _box_from_bbox(area.get('bbox'))
        if geom is not None:
            geoms.append(geom)
            geom_to_area[id(geom)] = area
    joins = []
    if geoms:
        tree = STRtree(geoms)
        for text in texts:
            center = bbox_center(text.get('bbox'))
            if center is None:
                continue
            point = Point(center[0], center[1])
            try:
                hits = tree.query(point)
            except Exception:
                hits = []
            for hit in hits:
                # Shapely 2 may return indexes depending on version/config; support both.
                area = None
                if isinstance(hit, int):
                    area = areas[hit] if 0 <= hit < len(areas) else None
                    geom = geoms[hit] if 0 <= hit < len(geoms) else None
                else:
                    area = geom_to_area.get(id(hit))
                    geom = hit
                if area is None or geom is None:
                    continue
                contains = bool(geom.contains(point) or geom.touches(point))
                if contains:
                    joins.append({
                        'text_id': text.get('target_id') or text.get('id'),
                        'area_id': area.get('area_id'),
                        'text': text.get('text'),
                        'text_role': text.get('role'),
                        'join_type': 'text_center_in_area_bbox',
                        'confidence': 0.55,
                    })
    payload = {
        'backend': 'strtree_spatial_join_backend',
        'status': 'ok' if joins else 'warning',
        'summary': {
            'area_count': len(areas),
            'text_count': len(texts),
            'join_count': len(joins),
        },
        'joins': joins[:10000],
        'todo': [
            'Use true polygon geometry instead of bbox geometry when available.',
            'Add per-file/page partitioning.',
            'Compare results against SPATIAL_INDEX_SERVICE bbox-bin candidates.',
            'Feed joins back into text role and area confidence fusion.',
        ],
        'warnings': ['STRtree currently indexes area bboxes, not exact polygons'],
    }
    return write_json_and_md(base, 'STRTREE_SPATIAL_JOIN', payload, _markdown(payload))


def _area_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for idx, area in enumerate(payload.get('polygons') or payload.get('candidates') or []):
        bbox = area.get('bbox')
        if isinstance(bbox, list) and len(bbox) == 4:
            rows.append({'area_id': area.get('polygon_id') or area.get('entity_id') or f'area:{idx}', 'bbox': bbox})
    return rows


def _text_records(text_roles: dict[str, Any], base: Path) -> list[dict[str, Any]]:
    rows = [item for item in text_roles.get('items') or [] if isinstance(item.get('bbox'), list) and len(item.get('bbox')) == 4]
    if rows:
        return rows
    fallback = []
    for ent in load_fileized_entities(base):
        if ent.get('entity_type') in TEXT_TYPES and isinstance(ent.get('bbox'), list) and len(ent.get('bbox')) == 4:
            fallback.append({
                'id': ent.get('id'),
                'target_id': ent.get('id'),
                'text': ent.get('text') or ent.get('value') or ent.get('content'),
                'role': 'unknown',
                'bbox': ent.get('bbox'),
            })
    return fallback


def _box_from_bbox(bbox: Any) -> Any | None:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(v) for v in bbox]
        return box(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
    except Exception:
        return None


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    return '\n'.join([
        '# STRtree Spatial Join',
        '',
        f"- Status: `{payload.get('status')}`",
        f"- Areas: `{s.get('area_count')}`",
        f"- Texts: `{s.get('text_count')}`",
        f"- Joins: `{s.get('join_count')}`",
        '',
    ])
