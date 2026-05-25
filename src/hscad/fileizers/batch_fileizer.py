"""Dispatch fileizer by extension."""
from __future__ import annotations

from pathlib import Path

from hscad.core.models import FileizedDrawing
from hscad.fileizers.base import detect_input_type
from hscad.fileizers.dwg_fileizer import DwgFileizer
from hscad.fileizers.dxf_fileizer import DxfFileizer
from hscad.fileizers.image_fileizer import ImageFileizer
from hscad.fileizers.pdf_fileizer import PdfFileizer


class BatchFileizer:
    def __init__(self) -> None:
        self.fileizers = [DwgFileizer(), DxfFileizer(), PdfFileizer(), ImageFileizer()]

    def fileize_one(self, path: str | Path, *, out_dir: str | Path | None = None) -> FileizedDrawing:
        for fileizer in self.fileizers:
            if fileizer.can_handle(path):
                return fileizer.fileize(path, out_dir=out_dir)
        from hscad.core.evidence import Evidence
        drawing = FileizedDrawing(input_path=str(path), input_type=detect_input_type(path))
        drawing.add_evidence(Evidence.error("unsupported input type", input_type=drawing.input_type))
        return drawing

    def fileize_many(self, paths: list[str | Path], *, out_dir: str | Path | None = None) -> list[FileizedDrawing]:
        return [self.fileize_one(path, out_dir=out_dir) for path in paths]
