from __future__ import annotations

from pathlib import Path
from typing import Any


class EzDxfAdapter:
    """Read-only DXF adapter for offline evidence extraction.

    This adapter intentionally does not mutate DXF/DWG files. It provides a safe
    fallback path when a drawing can be exported/fileized to DXF and ZWCAD COM is
    unavailable or too expensive for broad inspection.
    """

    def read_dxf_entities(self, path: str | Path) -> list[dict[str, Any]]:
        import ezdxf

        doc = ezdxf.readfile(str(path))
        msp = doc.modelspace()
        rows: list[dict[str, Any]] = []
        for entity in msp:
            rows.append(self._entity_to_dict(entity))
        return rows

    def layer_counts(self, path: str | Path) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self.read_dxf_entities(path):
            layer = str(row.get('layer') or '0')
            counts[layer] = counts.get(layer, 0) + 1
        return dict(sorted(counts.items()))

    def entity_counts(self, path: str | Path) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self.read_dxf_entities(path):
            kind = str(row.get('dxftype') or 'UNKNOWN')
            counts[kind] = counts.get(kind, 0) + 1
        return dict(sorted(counts.items()))

    def summary(self, path: str | Path) -> dict[str, Any]:
        rows = self.read_dxf_entities(path)
        layer_counts: dict[str, int] = {}
        entity_counts: dict[str, int] = {}
        for row in rows:
            layer = str(row.get('layer') or '0')
            kind = str(row.get('dxftype') or 'UNKNOWN')
            layer_counts[layer] = layer_counts.get(layer, 0) + 1
            entity_counts[kind] = entity_counts.get(kind, 0) + 1
        return {
            'source': str(path),
            'entity_count': len(rows),
            'layer_counts': dict(sorted(layer_counts.items())),
            'entity_counts': dict(sorted(entity_counts.items())),
            'entities': rows,
        }

    def _entity_to_dict(self, entity: Any) -> dict[str, Any]:
        row: dict[str, Any] = {
            'dxftype': entity.dxftype(),
            'layer': getattr(entity.dxf, 'layer', None),
            'handle': getattr(entity.dxf, 'handle', None),
            'color': getattr(entity.dxf, 'color', None),
            'linetype': getattr(entity.dxf, 'linetype', None),
        }
        self._attach_geometry(row, entity)
        return row

    def _attach_geometry(self, row: dict[str, Any], entity: Any) -> None:
        dxftype = row.get('dxftype')
        if dxftype == 'LINE':
            row['start'] = self._point(entity.dxf.start)
            row['end'] = self._point(entity.dxf.end)
        elif dxftype in {'LWPOLYLINE', 'POLYLINE'}:
            try:
                points = [[float(point[0]), float(point[1])] for point in entity.get_points()]
            except Exception:
                points = []
            row['points'] = points
            row['closed'] = bool(getattr(entity, 'closed', False))
        elif dxftype in {'TEXT', 'MTEXT'}:
            row['text'] = getattr(entity, 'text', None) or getattr(entity, 'plain_text', lambda: None)()
            insert = getattr(entity.dxf, 'insert', None)
            if insert is not None:
                row['insert'] = self._point(insert)
        elif dxftype == 'CIRCLE':
            row['center'] = self._point(entity.dxf.center)
            row['radius'] = float(entity.dxf.radius)
        elif dxftype == 'ARC':
            row['center'] = self._point(entity.dxf.center)
            row['radius'] = float(entity.dxf.radius)
            row['start_angle'] = float(entity.dxf.start_angle)
            row['end_angle'] = float(entity.dxf.end_angle)
        elif 'DIMENSION' in str(dxftype):
            row['measurement'] = getattr(entity.dxf, 'actual_measurement', None)
            row['text_override'] = getattr(entity.dxf, 'text', None)

    @staticmethod
    def _point(value: Any) -> list[float]:
        return [float(value[0]), float(value[1]), float(value[2]) if len(value) > 2 else 0.0]
