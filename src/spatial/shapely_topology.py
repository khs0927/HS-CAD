from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from src.spatial.geometry import as_point2d


class ShapelyTopologyAnalyzer:
    """Optional Shapely/GEOS topology analyzer for fileized CAD JSON.

    This module never makes Shapely mandatory. When Shapely is unavailable it
    returns a structured unavailable result so the HS-CAD pipeline can continue.
    """

    backend_id = 'shapely_topology'

    def is_available(self) -> tuple[bool, str]:
        if importlib.util.find_spec('shapely') is None:
            return False, 'shapely not installed'
        return True, 'shapely installed'

    def analyze_record(self, record: dict[str, Any]) -> dict[str, Any]:
        available, reason = self.is_available()
        file_id = str(record.get('file_id') or '')
        if not available:
            return {
                'file_id': file_id,
                'relative_path': record.get('relative_path'),
                'backend': self.backend_id,
                'status': 'unavailable',
                'reason': reason,
                'polygon_count': 0,
                'line_count': 0,
                'polygons': [],
                'signals': [],
            }
        from shapely.geometry import LineString
        from shapely.ops import linemerge, polygonize, unary_union

        line_strings = []
        for entity in record.get('entities') or []:
            for segment in _entity_segments(entity):
                if len(segment) >= 2:
                    line_strings.append(LineString(segment))
        if not line_strings:
            return {
                'file_id': file_id,
                'relative_path': record.get('relative_path'),
                'backend': self.backend_id,
                'status': 'ok',
                'reason': 'no linework candidates',
                'polygon_count': 0,
                'line_count': 0,
                'polygons': [],
                'signals': [],
            }
        merged = linemerge(unary_union(line_strings))
        polygons = list(polygonize(merged))
        rows = []
        for index, polygon in enumerate(polygons):
            if polygon.is_empty or polygon.area <= 0:
                continue
            min_x, min_y, max_x, max_y = polygon.bounds
            rows.append({
                'id': f'shapely_polygon:{file_id}:{index}',
                'area': round(float(polygon.area), 6),
                'bbox': [float(min_x), float(min_y), float(max_x), float(max_y)],
                'source': 'shapely_polygonize',
            })
        return {
            'file_id': file_id,
            'relative_path': record.get('relative_path'),
            'backend': self.backend_id,
            'status': 'ok',
            'reason': reason,
            'polygon_count': len(rows),
            'line_count': len(line_strings),
            'polygons': rows,
            'signals': [{'id': 'shapely_polygonize_area', 'score': 1.0, 'evidence': ['Shapely polygonize produced polygon candidates']}]
            if rows else [],
        }

    def analyze_json_file(self, path: str | Path) -> dict[str, Any]:
        source = Path(path)
        record = json.loads(source.read_text(encoding='utf-8'))
        result = self.analyze_record(record)
        result['source_json'] = str(source)
        return result

    def analyze_json_dir(self, json_dir: str | Path) -> dict[str, Any]:
        base = Path(json_dir)
        files = [self.analyze_json_file(path) for path in sorted(base.glob('*.json'))]
        polygons = []
        for item in files:
            polygons.extend(item.get('polygons') or [])
        status_counts: dict[str, int] = {}
        for item in files:
            status = str(item.get('status') or 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        return {
            'json_dir': str(base),
            'backend': self.backend_id,
            'file_count': len(files),
            'status_counts': status_counts,
            'polygon_count': len(polygons),
            'files': files,
            'polygons': polygons,
        }


def _entity_segments(entity: dict[str, Any]) -> list[list[tuple[float, float]]]:
    etype = str(entity.get('entity_type') or '').upper()
    if etype == 'LINE':
        start = as_point2d(entity.get('start'))
        end = as_point2d(entity.get('end'))
        if start and end:
            return [[(start.x, start.y), (end.x, end.y)]]
    if etype == 'POLYLINE':
        points = [as_point2d(point) for point in (entity.get('points') or [])]
        coords = [(point.x, point.y) for point in points if point is not None]
        if len(coords) >= 2:
            if entity.get('closed') and coords[0] != coords[-1]:
                coords.append(coords[0])
            return [coords]
    if etype == 'HATCH':
        rows = []
        for path in entity.get('paths') or []:
            points = [as_point2d(point) for point in (path.get('points') or [])]
            coords = [(point.x, point.y) for point in points if point is not None]
            if len(coords) >= 2:
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                rows.append(coords)
        return rows
    return []
