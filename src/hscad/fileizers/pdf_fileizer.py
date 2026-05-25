"""PDF fileizer skeleton with metadata-first fallback."""
from __future__ import annotations

from pathlib import Path

from hscad.core.evidence import ConfidenceScore, Evidence, EvidenceKind, EvidenceSource
from hscad.core.models import FileizedDrawing
from hscad.fileizers.base import Fileizer


class PdfFileizer(Fileizer):
    input_types = ("pdf",)

    def fileize(self, path: str | Path, *, out_dir: str | Path | None = None) -> FileizedDrawing:
        pdf_path = Path(path)
        metadata = {"fileizer": "PdfFileizer", "size_bytes": pdf_path.stat().st_size if pdf_path.exists() else None}
        page_count: int | None = None
        try:
            import fitz  # type: ignore
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            metadata["backend"] = "pymupdf"
            metadata["page_count"] = page_count
            doc.close()
        except Exception:
            metadata["backend"] = "metadata_only"
        drawing = FileizedDrawing(input_path=str(pdf_path), input_type="pdf", metadata=metadata)
        drawing.add_evidence(
            Evidence(
                source=EvidenceSource.PDF,
                kind=EvidenceKind.PLAN,
                payload={"page_count": page_count, "next_step": "render pages to image and OCR/vectorize"},
                confidence=ConfidenceScore.medium("PDF registered for downstream rendering"),
                tags=["fileized", "pdf", "plan_only"],
            )
        )
        return drawing
