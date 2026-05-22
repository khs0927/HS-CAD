from __future__ import annotations

from pathlib import Path
from typing import Any

from src.corpus.schema import FileizedDrawingRecord, layer_rows_from_entities, text_rows_from_entities
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
        }
        if etype == 'LINE':
            item['start'] = self._xyz(entity.dxf.start)
            item['end'] = self._xyz(entity.dxf.end)
        elif etype == 'TEXT':
            item['text'] = getattr(entity.dxf, 'text', None)
            item['insert'] = self._xyz(getattr(entity.dxf, 'insert', None))
        elif etype == 'MTEXT':
            item['text'] = getattr(entity, 'text', '')
            item['insert'] = self._xyz(getattr(entity.dxf, 'insert', None))
        elif etype == 'INSERT':
            item['name'] = getattr(entity.dxf, 'name', None)
            item['effective_name'] = getattr(entity.dxf, 'name', None)
            item['insert'] = self._xyz(getattr(entity.dxf, 'insert', None))
        elif etype == 'CIRCLE':
            item['center'] = self._xyz(entity.dxf.center)
            item['radius'] = getattr(entity.dxf, 'radius', None)
        elif 'POLYLINE' in etype:
            item['entity_type'] = 'POLYLINE'
        elif 'DIMENSION' in etype:
            item['entity_type'] = 'DIMENSION'
        return item

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
                entities=entities,
                texts=text_rows_from_entities(entities),
                metadata={'object_count': len(entities)},
            )
        except Exception as exc:
            return FileizedDrawingRecord.failed(
                file_id=file_id, source_path=src, relative_path=relative_path,
                extension=src.suffix, engine=self.engine_name, reason=str(exc),
            )
