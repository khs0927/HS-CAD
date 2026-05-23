from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.spatial.geometry import Point2D, as_point2d, bbox_from_points
from src.spatial.grid_index import IndexedPolygon, UniformGridIndex
from src.spatial.polygon import point_in_polygon


@dataclass
class TextInPolygonRelation:
    file_id: str
    text: str
    text_handle: str | None
    text_layer: str | None
    text_insert: list[float]
    polygon_handle: str | None
    polygon_layer: str | None
    polygon_point_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TextContainmentAnalyzer:
    def __init__(self, *, max_cells_per_polygon: int = 256):
        self.max_cells_per_polygon = max_cells_per_polygon

    def analyze_record(self, record: dict[str, Any]) -> dict[str, Any]:
        file_id = str(record.get('file_id') or '')
        entities = record.get('entities') or []
        polygons = self._indexed_polygons(entities)
        texts = self._texts(entities)
        index = UniformGridIndex(polygons, max_cells_per_polygon=self.max_cells_per_polygon)
        relations: list[TextInPolygonRelation] = []
        candidate_checks = 0
        brute_force_pairs = len(polygons) * len(texts)
        for text_entity, point in texts:
            for indexed_polygon in index.candidates(point):
                if not indexed_polygon.bbox.contains(point):
                    continue
                candidate_checks += 1
                if point_in_polygon(point, indexed_polygon.polygon):
                    relations.append(TextInPolygonRelation(
                        file_id=file_id,
                        text=str(text_entity.get('text') or ''),
                        text_handle=text_entity.get('handle'),
                        text_layer=text_entity.get('layer'),
                        text_insert=[point.x, point.y],
                        polygon_handle=indexed_polygon.entity.get('handle'),
                        polygon_layer=indexed_polygon.entity.get('layer'),
                        polygon_point_count=len(indexed_polygon.polygon),
                    ))
        stats = index.stats()
        stats.update({
            'text_count': len(texts),
            'brute_force_pairs': brute_force_pairs,
            'candidate_checks': candidate_checks,
            'reduction_ratio': round((1 - candidate_checks / brute_force_pairs) * 100, 4) if brute_force_pairs else 0,
        })
        return {
            'file_id': file_id,
            'relative_path': record.get('relative_path'),
            'relation_count': len(relations),
            'stats': stats,
            'relations': [relation.to_dict() for relation in relations],
        }

    def analyze_json_file(self, path: str | Path) -> dict[str, Any]:
        source = Path(path)
        record = json.loads(source.read_text(encoding='utf-8'))
        result = self.analyze_record(record)
        result['source_json'] = str(source)
        return result

    def analyze_json_dir(self, json_dir: str | Path) -> dict[str, Any]:
        base = Path(json_dir)
        results = [self.analyze_json_file(path) for path in sorted(base.glob('*.json'))]
        relations = []
        stats = {
            'file_count': len(results),
            'polygon_count': 0,
            'text_count': 0,
            'brute_force_pairs': 0,
            'candidate_checks': 0,
        }
        for result in results:
            relations.extend(result.get('relations') or [])
            file_stats = result.get('stats') or {}
            for key in stats:
                if key == 'file_count':
                    continue
                stats[key] += int(file_stats.get(key) or 0)
        stats['reduction_ratio'] = round((1 - stats['candidate_checks'] / stats['brute_force_pairs']) * 100, 4) if stats['brute_force_pairs'] else 0
        return {
            'json_dir': str(base),
            'file_count': len(results),
            'relation_count': len(relations),
            'stats': stats,
            'files': results,
            'relations': relations,
        }

    @staticmethod
    def _indexed_polygons(entities: list[dict[str, Any]]) -> list[IndexedPolygon]:
        rows: list[IndexedPolygon] = []
        for entity in entities:
            entity_type = str(entity.get('entity_type') or '').upper()
            if entity_type != 'POLYLINE':
                continue
            if not entity.get('closed'):
                continue
            points = [as_point2d(point) for point in (entity.get('points') or [])]
            polygon = [point for point in points if point is not None]
            bbox = bbox_from_points(polygon)
            if len(polygon) >= 3 and bbox is not None:
                rows.append(IndexedPolygon(index=len(rows), entity=entity, polygon=polygon, bbox=bbox))
        return rows

    @staticmethod
    def _texts(entities: list[dict[str, Any]]) -> list[tuple[dict[str, Any], Point2D]]:
        rows: list[tuple[dict[str, Any], Point2D]] = []
        for entity in entities:
            entity_type = str(entity.get('entity_type') or '').upper()
            if entity_type not in {'TEXT', 'MTEXT'}:
                continue
            point = as_point2d(entity.get('insert'))
            if point is not None:
                rows.append((entity, point))
        return rows
