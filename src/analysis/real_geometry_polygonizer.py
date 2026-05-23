from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import bbox_iou, load_fileized_entities, write_json_and_md

try:  # optional dependency
    from shapely.geometry import LineString, box
    from shapely.ops import polygonize_full, unary_union
    SHAPELY_AVAILABLE = True
    SHAPELY_ERROR = None
except Exception as exc:  # pragma: no cover
    LineString = None  # type: ignore
    box = None  # type: ignore
    polygonize_full = None  # type: ignore
    unary_union = None  # type: ignore
    SHAPELY_AVAILABLE = False
    SHAPELY_ERROR = str(exc)

LINE_TYPES = {'LINE', 'LWPOLYLINE', 'POLYLINE'}


def run_real_geometry_polygonizer(workspace: str | Path, *, min_area: float = 1.0) -> dict[str, Any]:
    """Optional Shapely polygonize_full backend.

    This is a best-effort implementation. If exact vertices are missing in fileized JSON,
    it falls back to bbox edges so that the pipeline still produces an audit artifact.
    """
    base = Path(workspace)
    entities = load_fileized_entities(base)
    if not SHAPELY_AVAILABLE:
        payload = {
            'backend': 'real_geometry_polygonizer',
            'status': 'unavailable',
            'reason': SHAPELY_ERROR,
            'summary': {'input_entity_count': len(entities), 'polygon_count': 0, 'dangle_count': 0, 'cut_edge_count': 0, 'invalid_ring_count': 0},
            'polygons': [],
            'quality': {},
            'warnings': ['Shapely is not installed; polygonize_full skipped'],
        }
        return write_json_and_md(base, 'REAL_GEOMETRY_POLYGONIZER', payload, _markdown(payload))

    lines = []
    source_refs = []
    for ent in entities:
        et = ent.get('entity_type')
        if et not in LINE_TYPES:
            continue
        geom = _entity_to_linestring(ent)
        if geom is not None:
            lines.append(geom)
            source_refs.append({'entity_id': ent.get('id'), 'layer': ent.get('layer'), 'entity_type': et})
    polygons: list[dict[str, Any]] = []
    dangle_count = 0
    cut_edge_count = 0
    invalid_ring_count = 0
    warnings: list[str] = []
    try:
        if lines:
            merged = unary_union(lines)
            result = polygonize_full(merged)
            poly_geoms, cut_edges, dangles, invalid_rings = result
            dangle_count = _geom_count(dangles)
            cut_edge_count = _geom_count(cut_edges)
            invalid_ring_count = _geom_count(invalid_rings)
            for idx, poly in enumerate(list(poly_geoms.geoms) if hasattr(poly_geoms, 'geoms') else list(poly_geoms)):
                area = float(getattr(poly, 'area', 0.0) or 0.0)
                if area < min_area:
                    continue
                minx, miny, maxx, maxy = [float(v) for v in poly.bounds]
                polygons.append({
                    'polygon_id': f'poly:{idx}',
                    'area': round(area, 6),
                    'bbox': [minx, miny, maxx, maxy],
                    'centroid': [round(float(poly.centroid.x), 6), round(float(poly.centroid.y), 6)],
                    'confidence': 0.72,
                    'source': 'shapely.polygonize_full',
                })
        else:
            warnings.append('No line-like entities available for polygonize_full')
    except Exception as exc:
        warnings.append(f'polygonize_full failed: {exc}')

    quality = {
        'line_count': len(lines),
        'polygon_count': len(polygons),
        'dangle_count': dangle_count,
        'cut_edge_count': cut_edge_count,
        'invalid_ring_count': invalid_ring_count,
        'fragment_quality_score': _quality_score(len(lines), len(polygons), dangle_count, cut_edge_count, invalid_ring_count),
    }
    payload = {
        'backend': 'real_geometry_polygonizer',
        'status': 'ok' if polygons else 'warning',
        'summary': {
            'input_entity_count': len(entities),
            **quality,
        },
        'polygons': polygons,
        'source_refs_sample': source_refs[:100],
        'quality': quality,
        'warnings': warnings,
        'todo': [
            'Replace bbox fallback geometry with true vertices from ezdxf payload when available.',
            'Add snap tolerance sweep before polygonize_full.',
            'Add arc/circle segmentation with configurable chord tolerance.',
            'Fuse polygon candidates with AREA_BOUNDARY_INFERENCE and RASTER_CONTOURS.',
        ],
    }
    return write_json_and_md(base, 'REAL_GEOMETRY_POLYGONIZER', payload, _markdown(payload))


def _entity_to_linestring(ent: dict[str, Any]) -> Any | None:
    points = ent.get('points') or ent.get('vertices') or ent.get('coords')
    if isinstance(points, list) and len(points) >= 2:
        parsed = []
        for pt in points:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                try:
                    parsed.append((float(pt[0]), float(pt[1])))
                except Exception:
                    pass
        if len(parsed) >= 2:
            return LineString(parsed)
    bbox = ent.get('bbox')
    if isinstance(bbox, list) and len(bbox) == 4:
        try:
            x1, y1, x2, y2 = [float(v) for v in bbox]
            if abs(x2 - x1) + abs(y2 - y1) > 0:
                return LineString([(x1, y1), (x2, y2)])
        except Exception:
            return None
    return None


def _geom_count(geom: Any) -> int:
    if geom is None:
        return 0
    if hasattr(geom, 'geoms'):
        return len(list(geom.geoms))
    return 1


def _quality_score(line_count: int, polygon_count: int, dangles: int, cuts: int, invalids: int) -> float:
    if line_count <= 0:
        return 0.0
    penalty = min(0.8, (dangles + cuts + invalids) / max(line_count, 1))
    polygon_bonus = min(0.3, polygon_count / max(line_count, 1))
    return round(max(0.0, min(1.0, 0.7 + polygon_bonus - penalty)), 6)


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    lines = [
        '# Real Geometry Polygonizer',
        '',
        f"- Status: `{payload.get('status')}`",
        f"- Input entities: `{s.get('input_entity_count')}`",
        f"- Lines: `{s.get('line_count')}`",
        f"- Polygons: `{s.get('polygon_count')}`",
        f"- Dangles: `{s.get('dangle_count')}`",
        f"- Cut edges: `{s.get('cut_edge_count')}`",
        f"- Invalid rings: `{s.get('invalid_ring_count')}`",
        f"- Quality score: `{s.get('fragment_quality_score')}`",
        '',
        '## Warnings',
        '',
    ]
    for warning in payload.get('warnings') or []:
        lines.append(f'- {warning}')
    if not payload.get('warnings'):
        lines.append('- None')
    lines.append('')
    return '\n'.join(lines)
