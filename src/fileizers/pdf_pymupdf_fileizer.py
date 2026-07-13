from __future__ import annotations

from pathlib import Path

from src.corpus.schema import FileizedDrawingRecord, layer_rows_from_entities, text_rows_from_entities
from src.fileizers.base import DrawingFileizer


class PDFPyMuPDFFileizer(DrawingFileizer):
    engine_name = 'pymupdf_complete'
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

            entities: list[dict] = []
            layouts: list[dict] = []
            warnings: list[dict] = []
            raster_image_count = 0
            with fitz.open(str(src)) as doc:
                page_count = len(doc)
                for page_index, page in enumerate(doc, start=1):
                    layout_name = f'PDF Page {page_index}'
                    rect = page.rect
                    page_entity_count = 1
                    entities.append(
                        {
                            'handle': f'p{page_index}',
                            'entity_type': 'PDF_PAGE',
                            'layer': 'PDF_PAGE',
                            'layout': layout_name,
                            'space': 'pdf',
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
                                'layout': layout_name,
                                'space': 'pdf',
                                'page_number': page_index,
                                'bbox': [float(block[0]), float(block[1]), float(block[2]), float(block[3])],
                                'text': text,
                            }
                        )
                        page_entity_count += 1

                    for image_index, image in enumerate(page.get_images(full=True), start=1):
                        xref = image[0] if image else image_index
                        entities.append(
                            {
                                'handle': f'p{page_index}-image-{xref}',
                                'entity_type': 'PDF_IMAGE',
                                'layer': 'PDF_IMAGE',
                                'layout': layout_name,
                                'space': 'pdf',
                                'page_number': page_index,
                                'xref': xref,
                                'requires_ocr': True,
                                'source_kind': 'embedded_pdf_image',
                            }
                        )
                        raster_image_count += 1
                        page_entity_count += 1
                    layouts.append(
                        {
                            'name': layout_name,
                            'space': 'pdf',
                            'available': True,
                            'entity_count': page_entity_count,
                            'page_number': page_index,
                        }
                    )

            texts = text_rows_from_entities(entities)
            if not texts:
                warnings.append({'type': 'no_text_extracted', 'reason': 'PDF may be scanned or image-only.'})
            if raster_image_count:
                warnings.append(
                    {
                        'type': 'pdf_images_require_ocr',
                        'count': raster_image_count,
                        'reason': 'Embedded raster images are recorded but have not been OCR-indexed.',
                    }
                )
            report = {
                'schema_version': 2,
                'scanner': self.engine_name,
                'entity_count': len(entities),
                'text_occurrence_count': len(texts),
                'layout_count': len(layouts),
                'requires_ocr_count': raster_image_count,
                'warning_count': len(warnings),
                'complete': not warnings and raster_image_count == 0,
                'coverage': {
                    'pdf_pages': bool(layouts),
                    'native_pdf_text': bool(texts),
                    'embedded_raster_ocr': raster_image_count == 0,
                },
            }
            return FileizedDrawingRecord(
                file_id=file_id,
                source_path=str(src),
                relative_path=str(relative_path),
                extension=src.suffix.lower(),
                status='ok',
                engine=self.engine_name,
                layers=layer_rows_from_entities(entities),
                entities=entities,
                texts=texts,
                layouts=layouts,
                extraction_report=report,
                metadata={
                    'page_count': page_count,
                    'object_count': len(entities),
                    'text_occurrence_count': len(texts),
                    'embedded_image_count': raster_image_count,
                },
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
