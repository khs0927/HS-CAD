from __future__ import annotations

from pathlib import Path

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from src.corpus.schema import (
    FileizedDrawingRecord,
    block_rows_from_entities,
    dimension_rows_from_entities,
    layer_rows_from_entities,
    text_rows_from_entities,
)
from src.fileizers.base import DrawingFileizer


class ZWCADDWGFileizer(DrawingFileizer):
    engine_name = 'zwcad_com'
    supported_extensions = ('.dwg',)

    def is_available(self) -> tuple[bool, str]:
        try:
            import comtypes.client  # noqa: F401
        except Exception as exc:
            return False, f'comtypes unavailable: {exc}'
        try:
            adapter = ZWCADCOMAdapter(visible=False)
            adapter.connect()
            return True, 'ZWCAD COM available'
        except Exception as exc:
            return False, f'ZWCAD COM unavailable: {exc}'

    def fileize(self, path: str | Path, *, file_id: str, relative_path: str | Path) -> FileizedDrawingRecord:
        src = Path(path)
        available, reason = self.is_available()
        if not available:
            return FileizedDrawingRecord.unavailable(
                file_id=file_id,
                source_path=src,
                relative_path=relative_path,
                extension=src.suffix,
                engine=self.engine_name,
                reason=reason,
            )
        adapter = ZWCADCOMAdapter(visible=False)
        try:
            adapter.connect()
            adapter.open_document(str(src))
            entities = adapter.scan_modelspace()
            warnings = list(adapter.warnings)
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
                metadata={'object_count': len(entities)},
                warnings=warnings,
            )
        except Exception as exc:
            return FileizedDrawingRecord.failed(
                file_id=file_id,
                source_path=src,
                relative_path=relative_path,
                extension=src.suffix,
                engine=self.engine_name,
                reason=str(exc),
            )
        finally:
            adapter.close()
