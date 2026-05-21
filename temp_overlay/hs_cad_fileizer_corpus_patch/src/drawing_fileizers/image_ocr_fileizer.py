from __future__ import annotations

from pathlib import Path

from .base import BaseDrawingFileizer
from .models import FileizedDrawingRecord
from .utils import stable_file_id


class ImageOCRFileizer(BaseDrawingFileizer):
    """Optional fileizer for paddleocr. Gracefully unavailable if dependency is missing."""

    SUPPORTED = {'.png', '.jpeg', '.jpg', '.tiff', '.tif'}

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.SUPPORTED

    def is_available(self) -> bool:
        try:
            __import__("paddleocr")
            return True
        except Exception:
            return False

    def get_name(self) -> str:
        return "paddleocr"

    def fileize(self, path: Path, out_dir: Path) -> FileizedDrawingRecord:
        path = Path(path)
        if not self.is_available():
            return FileizedDrawingRecord.failed(path, self.get_name(), "paddleocr is not installed", status="unavailable")

        # MVP: keep metadata-only for optional heavy adapters.
        # Extend this implementation in a follow-up commit once dependency is installed.
        try:
            st = path.stat()
            return FileizedDrawingRecord(
                file_id=stable_file_id(path),
                source_path=str(path),
                relative_path=path.name,
                extension=path.suffix.lower(),
                fileizer=self.get_name(),
                status="partial",
                metadata={"size_bytes": st.st_size},
                warnings=["Metadata-only optional fileizer stub. Extend for full extraction."],
            )
        except Exception as exc:
            return FileizedDrawingRecord.failed(path, self.get_name(), str(exc))
