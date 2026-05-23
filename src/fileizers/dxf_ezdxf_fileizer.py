from __future__ import annotations

from pathlib import Path
from typing import Any

from src.corpus.schema import (
    FileizedDrawingRecord,
    block_rows_from_entities,
    dimension_rows_from_entities,
    layer_rows_from_entities,
    text_rows_from_entities,
)
from src.fileizers.base import DrawingFileizer


class DXFEzdxfFileizer(DrawingFileizer):
    engine_name = 'ezdxf'
    supported_extensions = ('.dxf',)

    def is_available(self) -> tuple[bool, str]:
        try:
            import ezdxf  # noqa: F401
            return True, 'ezdxf available'
        except Exception as exc:
            return False, f'ezdxf unavailable: {exc}'

    @staticmethod
    def _xyz(value: Any) -> list[float] | None:
        try:
            return [float(value[0]), float(value[1]), float(value[2] if len(value) > 2 else 0.0)]
        except Exception:
            return None

    def _entity_to_dict(self, entity: Any) -> dict[str, Any]:
        etype = str(entity.dxftype()).upper()
        item: dict[str, Any] = {
            'handle': getattr(entity.dxf, 'handle', None),
            'entity_type': etype,
            'layer': getattr(entity.dxf, 'layer', None),
            'color': getattr(entity.dxf, 'color', None),
            'linetype': getattr(entity.dxf, 'linetype', None),
        }
        if etype == 'LINE':
            item['start'] = self._xyz(entity.dxf.start)
            item['end'] = self._xyz(entity.dxf.end)
        elif etype == 'TEXT':
            item['text'] = getattr(entity.dxf, 'text', None)
            item['insert'] = self._xyz(getattr(entity.dxf, 'insert', None))
            item['height'] = getattr(entity.dxf, 'height', None)
            item['rotation'] = getattr(entity.dxf, 'rotation', None)
            item['style_name'] = getattr(entity.dxf, 'style', None)
        elif etype == 'MTEXT':
            item['text'] = getattr(entity, 'text', '')
            item['insert'] = self._xyz(getattr(entity.dxf, 'insert', None))
            item['height'] = getattr(entity.dxf, 'char_height', None)
            item['rotation'] = getattr(entity.dxf, 'rotation', None)
            item['style_name'] = getattr(entity.dxf, 'style', None)
        elif etype == 'INSERT':
            item['name'] = getattr(entity.dxf, 'name', None)
            item['effective_name'] = getattr(entity.dxf, 'name', None)
            item['insert'] = self._xyz(getattr(entity.dxf, 'insert', None))
            item['rotation'] = getattr(entity.dxf, 'rotation', None)
            item['x_scale'] = getattr(entity.dxf, 'xscale', None)
            item['y_scale'] = getattr(entity.dxf, 'yscale', None)
            item['z_scale'] = getattr(entity.dxf, 'zscale', None)
        elif etype == 'CIRCLE':
            item['center'] = self._xyz(entity.dxf.center)
            item['radius'] = getattr(entity.dxf, 'radius', None)
        elif etype == 'ARC':
            item['center'] = self._xyz(entity.dxf.center)
            item['radius'] = getattr(entity.dxf, 'radius', None)
            item['start_angle'] = getattr(entity.dxf, 'start_angle', None)
            item['end_angle'] = getattr(entity.dxf, 'end_angle', None)
        elif etype == 'LWPOLYLINE':
            item['entity_type'] = 'POLYLINE'
            try:
                item['points'] = [[float(x), float(y), 0.0] for x, y, *_ in entity.get_points()]
            except Exception:
                item['points'] = []
            item['closed'] = bool(getattr(entity, 'closed', False))
        elif etype == 'POLYLINE':
            item['entity_type'] = 'POLYLINE'
            try:
                item['points'] = [self._xyz(vertex.dxf.location) for vertex in entity.vertices]
            except Exception:
                item['points'] = []
            item['closed'] = bool(getattr(entity, 'is_closed', False))
        elif etype == 'HATCH':
            item['pattern_name'] = getattr(entity.dxf, 'pattern_name', None)
            item['solid_fill'] = getattr(entity.dxf, 'solid_fill', None)
            item['boundary_path_count'] = len(getattr(entity, 'paths', []) or [])
            item['boundary_hint'] = True
            item['paths'] = self._hatch_paths(entity)
        elif 'DIMENSION' in etype:
            item['entity_type'] = 'DIMENSION'
            item['text_override'] = getattr(entity.dxf, 'text', None)
            item['measurement'] = getattr(entity, 'get_measurement', lambda: None)()
        return item

    def _hatch_paths(self, entity: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in list(getattr(entity, 'paths', []) or []):
            points = self._hatch_path_points(path)
            rows.append({'path_type': path.__class__.__name__, 'points': points})
        return rows

    def _hatch_path_points(self, path: Any) -> list[list[float]]:
        points: list[list[float]] = []
        for vertex in list(getattr(path, 'vertices', []) or []):
            xyz = self._xyz(vertex)
            if xyz is not None:
                points.append(xyz)
        if points:
            return points
        for edge in list(getattr(path, 'edges', []) or []):
            edge_points = self._hatch_edge_points(edge)
            if points and edge_points and points[-1][:2] == edge_points[0][:2]:
                points.extend(edge_points[1:])
            else:
                points.extend(edge_points)
        return points

    def _hatch_edge_points(self, edge: Any) -> list[list[float]]:
        edge_name = edge.__class__.__name__.lower()
        if 'line' in edge_name:
            start = self._xyz(getattr(edge, 'start', None))
            end = self._xyz(getattr(edge, 'end', None))
            return [p for p in [start, end] if p is not None]
        if 'arc' in edge_name:
            center = self._xyz(getattr(edge, 'center', None))
            radius = getattr(edge, 'radius', None)
            start_angle = getattr(edge, 'start_angle', None)
            end_angle = getattr(edge, 'end_angle', None)
            if center is None or radius is None or start_angle is None or end_angle is None:
                return []
            import math
            start = math.radians(float(start_angle))
            end = math.radians(float(end_angle))
            if end < start:
                end += math.tau
            steps = 16
            return [
                [center[0] + math.cos(start + (end - start) * i / (steps - 1)) * float(radius),
                 center[1] + math.sin(start + (end - start) * i / (steps - 1)) * float(radius),
                 0.0]
                for i in range(steps)
            ]
        return []

    def fileize(self, path: str | Path, *, file_id: str, relative_path: str | Path) -> FileizedDrawingRecord:
        src = Path(path)
        available, reason = self.is_available()
        if not available:
            return FileizedDrawingRecord.unavailable(
                file_id=file_id, source_path=src, relative_path=relative_path,
                extension=src.suffix, engine=self.engine_name, reason=reason,
            )
        try:
            import ezdxf
            doc = ezdxf.readfile(str(src))
            entities = [self._entity_to_dict(entity) for entity in doc.modelspace()]
            return FileizedDrawingRecord(
                file_id=file_id,
                source_path=str(src),
                relative_path=str(relative_path),
                extension=src.suffix.lower(),
                status='ok',
                engine=self.engine_name,
                layers=layer_rows_from_entities(entities),
                blocks=block_rows_from_entities(entities),
                entities=entities,
                texts=text_rows_from_entities(entities),
                dimensions=dimension_rows_from_entities(entities),
                metadata={'object_count': len(entities), 'dxf_version': getattr(doc, 'dxfversion', None)},
            )
        except Exception as exc:
            return FileizedDrawingRecord.failed(
                file_id=file_id, source_path=src, relative_path=relative_path,
                extension=src.suffix, engine=self.engine_name, reason=str(exc),
            )
