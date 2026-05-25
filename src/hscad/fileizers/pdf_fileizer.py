"""PDF fileizer boundary.

Full PDF raster/text extraction is intentionally deferred to dedicated optional
adapters. This module emits explicit evidence instead of guessing.
"""
from __future__ import annotations

from pathlib import Path

from hscad.core.evidence import make_evidence
from hscad.core.models import FileizedDrawing


class PdfFileizer:
    def fileize(self, input_path: str | Path, out_dir: str | Path | None = None) -> FileizedDrawing:
        path = Path(input_path)
        evidence = make_evidence(
            "fileizer.pdf.boundary",
            "adapter_boundary",
            "PDF input registered; raster/text extraction adapter must be enabled for geometry",
            module="hscad.fileizers.pdf_fileizer",
            source_id=str(path),
            confidence=0.35,
            reason="plan-only boundary",
            data={"recommended_adapters": ["pymupdf", "pdfplumber", "opencv", "ocr"]},
        )
        return FileizedDrawing(str(path), "pdf", [], {"adapter_boundary": True}, [evidence], ["PDF extraction adapter not enabled"])
