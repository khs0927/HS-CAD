"""Image fileizer skeleton.

This records image dimensions when Pillow or OpenCV is available and leaves the
actual vectorization to the vision pipeline.
"""
from __future__ import annotations

from pathlib import Path

from hscad.core.evidence import ConfidenceScore, Evidence, EvidenceKind, EvidenceSource
from hscad.core.models import FileizedDrawing
from hscad.fileizers.base import Fileizer


class ImageFileizer(Fileizer):
    input_types = ("png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp")

    def fileize(self, path: str | Path, *, out_dir: str | Path | None = None) -> FileizedDrawing:
        image_path = Path(path)
        metadata = {"fileizer": "ImageFileizer", "size_bytes": image_path.stat().st_size if image_path.exists() else None}
        try:
            from PIL import Image  # type: ignore
            with Image.open(image_path) as img:
                metadata.update({"backend": "pillow", "width": img.width, "height": img.height, "mode": img.mode})
        except Exception:
            metadata["backend"] = "metadata_only"
        drawing = FileizedDrawing(input_path=str(image_path), input_type=image_path.suffix.lower().lstrip("."), metadata=metadata)
        drawing.add_evidence(
            Evidence(
                source=EvidenceSource.IMAGE,
                kind=EvidenceKind.PLAN,
                payload={"next_step": "deskew/binarize/line-detect/OCR/fusion", **metadata},
                confidence=ConfidenceScore.medium("image registered for downstream vision pipeline"),
                tags=["fileized", "image", "plan_only"],
            )
        )
        return drawing
