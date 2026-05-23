from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.spatial.geometry import Point2D, as_point2d, bbox_from_points
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
    def analyze_record(self, record: dict[str, Any]) -> dict[str, Any]:
        file_id = str(record.get('file_id') or '')
        entities = record.get('entities') or []
        polygons = self._closed_polygons(entities)
        texts = self._texts(entities)
        relations: list[TextInPolygonRelation] = []
        for text_entity, point in texts:
            for polygon_entity, polygon in polygons:
                bbox = bbox_from_points(polygon)
                if bbox is not None and not bbox.contains(point):
                    continue
                if point_in_polygon(point, polygon):
                    relations.append(TextInPolygonRelation(
                        file_id=file_id,
                        text=str(text_entity.get('text') or ''),
                        text_handle=text_entity.get('handle'),
                        text_layer=text_entity.get('layer'),
                        text_insert=[point.x, point.y],
                        polygon_handle=polygon_entity.get('handle'),
                        polygon_layer=polygon_entity.get('layer'),
                        polygon_point_count=len(polygon),
                    ))
        return {
            'file_id': file_id,
            'relative_path': record.get('relative_path'),
            'relation_count': len(relations),
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
        for result in results:
            relations.extend(result.get('relations') or [])
        return {
            'json_dir': str(base),
            'file_count': len(results),
            'relation_count': len(relations),
            'files': results,
            'relations': relations,
        }

    @staticmethod
    def _closed_polygons(entities: list[dict[str, Any]]) -> list[tuple[dict[str, Any], list[Point2D]]]:
        rows: list[tuple[dict[str, Any], list[Point2D]]] = []
        for entity in entities:
            entity_type = str(entity.get('entity_type') or '').upper()
            if entity_type != 'POLYLINE':
                continue
            if not entity.get('closed'):
                continue
            points = [as_point2d(point) for point in (entity.get('points') or [])]
            polygon = [point for point in points if point is not None]
            if len(polygon) >= 3:
                rows.append((entity, polygon))
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
