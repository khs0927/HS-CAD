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


def extract_boundary_candidates(
    entities: list[dict[str, Any]], *, tolerance: float = 1e-3, circle_segments: int = 48
) -> list[BoundaryCandidate]:
    rows: list[BoundaryCandidate] = []
    rows.extend(_closed_polylines(entities))
    rows.extend(_hatch_boundaries(entities))
    rows.extend(_circles(entities, circle_segments=circle_segments))
    rows.extend(_segment_loops(entities, tolerance=tolerance, arc_segments=max(8, circle_segments // 6)))
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


def _hatch_boundaries(entities: list[dict[str, Any]]) -> list[BoundaryCandidate]:
    rows: list[BoundaryCandidate] = []
    for entity in entities:
        if str(entity.get('entity_type') or '').upper() != 'HATCH':
            continue
        for path_index, path in enumerate(entity.get('paths') or []):
            points = [as_point2d(point) for point in (path.get('points') or [])]
            polygon = [point for point in points if point is not None]
            if len(polygon) >= 3:
                hatch_entity = dict(entity)
                hatch_entity['handle'] = f"{entity.get('handle')}:path{path_index}"
                hatch_entity['path_index'] = path_index
                rows.append(BoundaryCandidate(entity=hatch_entity, polygon=polygon, source_type='hatch_boundary'))
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


def _segment_loops(entities: list[dict[str, Any]], *, tolerance: float, arc_segments: int) -> list[BoundaryCandidate]:
    segments = _segments_from_lines_and_arcs(entities, arc_segments=arc_segments)
    unused = set(range(len(segments)))
    loops: list[BoundaryCandidate] = []
    while unused:
        first_index = unused.pop()
        first_entity, points = segments[first_index]
        chain_entities = [first_entity]
        chain = list(points)
        current = chain[-1]
        changed = True
        while changed and len(chain) < 10000:
            changed = False
            if _same_point(current, chain[0], tolerance) and len(chain) >= 4:
                loop_entity = _merged_segment_loop_entity(chain_entities)
                source_type = 'line_loop' if all(str(e.get('entity_type')).upper() == 'LINE' for e in chain_entities) else 'segment_loop'
                loops.append(BoundaryCandidate(entity=loop_entity, polygon=chain[:-1], source_type=source_type))
                break
            for candidate_index in list(unused):
                entity, points = segments[candidate_index]
                start = points[0]
                end = points[-1]
                if _same_point(current, start, tolerance):
                    unused.remove(candidate_index)
                    chain_entities.append(entity)
                    chain.extend(points[1:])
                    current = chain[-1]
                    changed = True
                    break
                if _same_point(current, end, tolerance):
                    unused.remove(candidate_index)
                    chain_entities.append(entity)
                    chain.extend(list(reversed(points[:-1])))
                    current = chain[-1]
                    changed = True
                    break
    return loops


def _segments_from_lines_and_arcs(entities: list[dict[str, Any]], *, arc_segments: int) -> list[tuple[dict[str, Any], list[Point2D]]]:
    segments: list[tuple[dict[str, Any], list[Point2D]]] = []
    for entity in entities:
        etype = str(entity.get('entity_type') or '').upper()
        if etype == 'LINE':
            start = as_point2d(entity.get('start'))
            end = as_point2d(entity.get('end'))
            if start is not None and end is not None and not _same_point(start, end, 1e-12):
                segments.append((entity, [start, end]))
        elif etype == 'ARC':
            points = _arc_points(entity, segments=arc_segments)
            if len(points) >= 2:
                segments.append((entity, points))
    return segments


def _arc_points(entity: dict[str, Any], *, segments: int) -> list[Point2D]:
    center = as_point2d(entity.get('center'))
    if center is None:
        return []
    try:
        radius = float(entity.get('radius'))
        start_angle = math.radians(float(entity.get('start_angle')))
        end_angle = math.radians(float(entity.get('end_angle')))
    except Exception:
        return []
    if radius <= 0:
        return []
    if end_angle < start_angle:
        end_angle += math.tau
    steps = max(2, segments)
    return [
        Point2D(center.x + math.cos(start_angle + (end_angle - start_angle) * i / (steps - 1)) * radius,
                center.y + math.sin(start_angle + (end_angle - start_angle) * i / (steps - 1)) * radius)
        for i in range(steps)
    ]


def _merged_segment_loop_entity(entities: list[dict[str, Any]]) -> dict[str, Any]:
    layers = sorted({str(entity.get('layer')) for entity in entities if entity.get('layer') is not None})
    handles = [str(entity.get('handle')) for entity in entities if entity.get('handle') is not None]
    source_types = sorted({str(entity.get('entity_type')).upper() for entity in entities})
    return {
        'handle': '+'.join(handles[:8]) if handles else None,
        'entity_type': 'BOUNDARY',
        'layer': layers[0] if len(layers) == 1 else ','.join(layers[:5]),
        'source_entity_type': '+'.join(source_types),
        'segment_count': len(entities),
    }


def _same_point(a: Point2D, b: Point2D, tolerance: float) -> bool:
    return abs(a.x - b.x) <= tolerance and abs(a.y - b.y) <= tolerance
