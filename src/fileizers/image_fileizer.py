from __future__ import annotations

from pathlib import Path

from src.corpus.schema import FileizedDrawingRecord
from src.fileizers.base import DrawingFileizer


class ImageMetadataFileizer(DrawingFileizer):
    engine_name = 'pillow_image_metadata'
    supported_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')

    def is_available(self) -> tuple[bool, str]:
        try:
            from PIL import Image  # noqa: F401
            return True, 'Pillow available'
        except Exception as exc:
            return False, f'Pillow unavailable: {exc}'

    def fileize(self, path: str | Path, *, file_id: str, relative_path: str | Path) -> FileizedDrawingRecord:
        src = Path(path)
        available, reason = self.is_available()
        if not available:
            return FileizedDrawingRecord.unavailable(
                file_id=file_id, source_path=src, relative_path=relative_path,
                extension=src.suffix, engine=self.engine_name, reason=reason,
            )
        try:
            from PIL import Image
            with Image.open(src) as img:
                width, height = img.size
                mode = img.mode
                fmt = img.format
            entity = {
                'handle': 'image-1',
                'entity_type': 'IMAGE',
                'layer': 'IMAGE',
                'width': width,
                'height': height,
                'mode': mode,
                'format': fmt,
            }
            return FileizedDrawingRecord(
                file_id=file_id,
                source_path=str(src),
                relative_path=str(relative_path),
                extension=src.suffix.lower(),
                status='ok',
                engine=self.engine_name,
                layers=[{'name': 'IMAGE', 'entity_count': 1}],
                entities=[entity],
                metadata={'width': width, 'height': height, 'mode': mode, 'format': fmt, 'object_count': 1},
                warnings=[{'type': 'metadata_only'}],
            )
        except Exception as exc:
            return FileizedDrawingRecord.failed(
                file_id=file_id, source_path=src, relative_path=relative_path,
                extension=src.suffix, engine=self.engine_name, reason=str(exc),
            )
