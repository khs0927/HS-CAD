from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from src.spatial.geometry import Point2D, as_point2d, bbox_from_points
from src.spatial.grid_index import IndexedPolygon


@dataclass(frozen=True)
class BoundaryCandidate:
    entity: dict[str, Any]
    polygon: list[Point2D]
    source_type: str


def extract_boundary_candidates(entities: list[dict[str, Any]], *, tolerance: float = 1e-3, circle_segments: int = 48) -> list[BoundaryCandidate]:
    rows: list[BoundaryCandidate] = []
    rows.extend(_closed_polylines(entities))
    rows.extend(_circles(entities, circle_segments=circle_segments))
    rows.extend(_line_loops(entities, tolerance=tolerance))
    return rows


def to_indexed_polygons(candidates: list[BoundaryCandidate]) -> list[IndexedPolygon]:
    rows: list[IndexedPolygon] = []
    for candidate in candidates:
        bbox = bbox_from_points(candidate.polygon)
        if bbox is None or len(candidate.polygon) < 3:
            continue
        entity = dict(candidate.entity)
        entity.setdefault('boundary_source_type', candidate.source_type)
        rows.append(IndexedPolygon(index=len(rows), entity=entity, polygon=candidate.polygon, bbox=bbox))
    return rows


def _closed_polylines(entities: list[dict[str, Any]]) -> list[BoundaryCandidate]:
    rows: list[BoundaryCandidate] = []
    for entity in entities:
        if str(entity.get('entity_type') or '').upper() != 'POLYLINE':
            continue
        if not entity.get('closed'):
            continue
        points = [as_point2d(point) for point in (entity.get('points') or [])]
        polygon = [point for point in points if point is not None]
        if len(polygon) >= 3:
            rows.append(BoundaryCandidate(entity=entity, polygon=polygon, source_type='closed_polyline'))
    return rows


def _circles(entities: list[dict[str, Any]], *, circle_segments: int) -> list[BoundaryCandidate]:
    rows: list[BoundaryCandidate] = []
    segment_count = max(12, circle_segments)
    for entity in entities:
        if str(entity.get('entity_type') or '').upper() != 'CIRCLE':
            continue
        center = as_point2d(entity.get('center'))
        try:
            radius = float(entity.get('radius'))
        except Exception:
            radius = 0.0
        if center is None or radius <= 0:
            continue
        polygon = []
        for index in range(segment_count):
            angle = math.tau * index / segment_count
            polygon.append(Point2D(center.x + math.cos(angle) * radius, center.y + math.sin(angle) * radius))
        rows.append(BoundaryCandidate(entity=entity, polygon=polygon, source_type='circle_approx'))
    return rows


def _line_loops(entities: list[dict[str, Any]], *, tolerance: float) -> list[BoundaryCandidate]:
    segments: list[tuple[dict[str, Any], Point2D, Point2D]] = []
    for entity in entities:
        if str(entity.get('entity_type') or '').upper() != 'LINE':
            continue
        start = as_point2d(entity.get('start'))
        end = as_point2d(entity.get('end'))
        if start is None or end is None:
            continue
        if _same_point(start, end, tolerance):
            continue
        segments.append((entity, start, end))
    unused = set(range(len(segments)))
    loops: list[BoundaryCandidate] = []
    while unused:
        first_index = unused.pop()
        first_entity, start, end = segments[first_index]
        chain_entities = [first_entity]
        chain = [start, end]
        current = end
        changed = True
        while changed and len(chain) < 10000:
            changed = False
            if _same_point(current, chain[0], tolerance) and len(chain) >= 4:
                loop_entity = _merged_line_loop_entity(chain_entities)
                loops.append(BoundaryCandidate(entity=loop_entity, polygon=chain[:-1], source_type='line_loop'))
                break
            for candidate_index in list(unused):
                entity, a, b = segments[candidate_index]
                if _same_point(current, a, tolerance):
                    unused.remove(candidate_index)
                    chain_entities.append(entity)
                    chain.append(b)
                    current = b
                    changed = True
                    break
                if _same_point(current, b, tolerance):
                    unused.remove(candidate_index)
                    chain_entities.append(entity)
                    chain.append(a)
                    current = a
                    changed = True
                    break
    return loops


def _merged_line_loop_entity(entities: list[dict[str, Any]]) -> dict[str, Any]:
    layers = sorted({str(entity.get('layer')) for entity in entities if entity.get('layer') is not None})
    handles = [str(entity.get('handle')) for entity in entities if entity.get('handle') is not None]
    return {
        'handle': '+'.join(handles[:8]) if handles else None,
        'entity_type': 'BOUNDARY',
        'layer': layers[0] if len(layers) == 1 else ','.join(layers[:5]),
        'source_entity_type': 'LINE',
        'segment_count': len(entities),
    }


def _same_point(a: Point2D, b: Point2D, tolerance: float) -> bool:
    return abs(a.x - b.x) <= tolerance and abs(a.y - b.y) <= tolerance
