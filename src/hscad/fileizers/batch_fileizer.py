"""Format-dispatching fileizer."""
from __future__ import annotations

from pathlib import Path

from hscad.core.evidence import make_evidence
from hscad.core.models import FileizedDrawing
from hscad.fileizers.dwg_fileizer import DwgFileizer
from hscad.fileizers.dxf_fileizer import DxfFileizer
from hscad.fileizers.image_fileizer import ImageFileizer
from hscad.fileizers.pdf_fileizer import PdfFileizer


class BatchFileizer:
    def fileize_one(self, input_path: str | Path, out_dir: str | Path | None = None) -> FileizedDrawing:
        path = Path(input_path)
        suffix = path.suffix.lower()
        if suffix == ".dxf":
            return DxfFileizer().fileize(path, out_dir=out_dir)
        if suffix == ".dwg":
            return DwgFileizer().fileize(path, out_dir=out_dir)
        if suffix == ".pdf":
            return PdfFileizer().fileize(path, out_dir=out_dir)
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}:
            return ImageFileizer().fileize(path, out_dir=out_dir)
        evidence = make_evidence("fileizer.unsupported", "unsupported_input", f"Unsupported input extension: {suffix}", module="hscad.fileizers.batch_fileizer", source_id=str(path), confidence=0.1)
        return FileizedDrawing(str(path), suffix.lstrip(".") or "unknown", [], {"unsupported": True}, [evidence], [f"Unsupported extension: {suffix}"])

    def fileize_many(self, paths: list[str | Path], out_dir: str | Path | None = None) -> list[FileizedDrawing]:
        return [self.fileize_one(path, out_dir=out_dir) for path in paths]
