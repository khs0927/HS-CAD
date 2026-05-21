from __future__ import annotations

from pathlib import Path

from .base import BaseDrawingFileizer
from .dxf_fileizer import DXFFileizer
from .dwg_libredwg_fileizer import LibreDWGFileizer
from .dwg_zwcad_fileizer import ZWCADCOMFileizer
from .pdf_docling_fileizer import DoclingFileizer
from .pdf_pymupdf_fileizer import PyMuPDFFileizer
from .document_unstructured_fileizer import UnstructuredFileizer
from .image_ocr_fileizer import ImageOCRFileizer
from .ifc_fileizer import IFCFileizer


class FileizerRegistry:
    """Selects the best available fileizer for a file extension."""

    def __init__(self) -> None:
        self.fileizers: list[BaseDrawingFileizer] = [
            DXFFileizer(),
            LibreDWGFileizer(),
            ZWCADCOMFileizer(),
            DoclingFileizer(),
            PyMuPDFFileizer(),
            UnstructuredFileizer(),
            ImageOCRFileizer(),
            IFCFileizer(),
        ]

    def candidates_for(self, path: Path) -> list[BaseDrawingFileizer]:
        ext = path.suffix.lower()

        if ext == ".dxf":
            order = ["ezdxf"]
        elif ext == ".dwg":
            order = ["libredwg-cli", "zwcad-com"]
        elif ext == ".pdf":
            order = ["docling", "fitz", "unstructured", "paddleocr"]
        elif ext in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
            order = ["paddleocr", "docling"]
        elif ext == ".ifc":
            order = ["ifcopenshell"]
        elif ext in {".docx", ".pptx", ".xlsx", ".html", ".htm", ".txt"}:
            order = ["docling", "unstructured"]
        else:
            order = []

        by_name = {f.get_name(): f for f in self.fileizers}
        return [by_name[name] for name in order if name in by_name and by_name[name].supports(path)]

    def best_for(self, path: Path) -> BaseDrawingFileizer | None:
        for fileizer in self.candidates_for(path):
            if fileizer.is_available():
                return fileizer
        candidates = self.candidates_for(path)
        return candidates[0] if candidates else None

    def availability_report(self) -> list[dict[str, object]]:
        return [
            {
                "name": f.get_name(),
                "available": f.is_available(),
                "version": f.get_version(),
                "class": f.__class__.__name__,
            }
            for f in self.fileizers
        ]
