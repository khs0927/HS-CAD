"""Image fileizer boundary for scanned/raster drawings."""
from __future__ import annotations

from pathlib import Path

from hscad.core.evidence import make_evidence
from hscad.core.models import FileizedDrawing


class ImageFileizer:
    def fileize(self, input_path: str | Path, out_dir: str | Path | None = None) -> FileizedDrawing:
        path = Path(input_path)
        evidence = make_evidence(
            "fileizer.image.boundary",
            "adapter_boundary",
            "Image input registered; OpenCV/MLSD/OCR/VLM adapters should generate geometry candidates",
            module="hscad.fileizers.image_fileizer",
            source_id=str(path),
            confidence=0.35,
            reason="plan-only boundary",
            data={"coordinate_note": "image top-left origin must be normalized to CAD bottom-left origin"},
        )
        return FileizedDrawing(str(path), "image", [], {"adapter_boundary": True}, [evidence], ["Image geometry extraction adapter not enabled"])
