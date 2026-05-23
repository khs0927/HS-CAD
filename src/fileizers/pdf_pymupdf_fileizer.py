from __future__ import annotations

from pathlib import Path

from src.corpus.schema import FileizedDrawingRecord, layer_rows_from_entities, text_rows_from_entities
from src.fileizers.base import DrawingFileizer


class PDFPyMuPDFFileizer(DrawingFileizer):
    engine_name = 'pymupdf'
    supported_extensions = ('.pdf',)

    def is_available(self) -> tuple[bool, str]:
        try:
            import fitz  # noqa: F401
            return True, 'PyMuPDF available'
        except Exception as exc:
            return False, f'PyMuPDF unavailable: {exc}'

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
        try:
            import fitz

            doc = fitz.open(str(src))
            entities: list[dict] = []
            warnings: list[dict] = []
            for page_index, page in enumerate(doc, start=1):
                rect = page.rect
                entities.append(
                    {
                        'handle': f'p{page_index}',
                        'entity_type': 'PDF_PAGE',
                        'layer': 'PDF_PAGE',
                        'page_number': page_index,
                        'bbox': [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)],
                        'width': float(rect.width),
                        'height': float(rect.height),
                    }
                )
                for block in page.get_text('blocks'):
                    if len(block) < 5:
                        continue
                    text = str(block[4]).strip()
                    if not text:
                        continue
                    block_no = block[5] if len(block) > 5 else len(entities)
                    entities.append(
                        {
                            'handle': f'p{page_index}-b{block_no}',
                            'entity_type': 'TEXT',
                            'layer': 'PDF_TEXT',
                            'page_number': page_index,
                            'bbox': [float(block[0]), float(block[1]), float(block[2]), float(block[3])],
                            'text': text,
                        }
                    )
            if not any(item.get('entity_type') == 'TEXT' for item in entities):
                warnings.append({'type': 'no_text_extracted', 'reason': 'PDF may be scanned or image-only.'})
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
                metadata={'page_count': len(doc), 'object_count': len(entities)},
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
