from __future__ import annotations

from pathlib import Path

from .base import BaseDrawingFileizer
from .models import FileizedDrawingRecord


class ZWCADCOMFileizer(BaseDrawingFileizer):
    """Optional ZWCAD COM fileizer stub.

    The actual extraction should reuse the existing HS-CAD ZWCAD COM adapter.
    This implementation is intentionally conservative and never saves source DWG.
    """

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() == ".dwg"

    def is_available(self) -> bool:
        try:
            import comtypes.client  # noqa: F401

            return True
        except Exception:
            return False

    def get_name(self) -> str:
        return "zwcad-com"

    def fileize(self, path: Path, out_dir: Path) -> FileizedDrawingRecord:
        if not self.is_available():
            return FileizedDrawingRecord.failed(path, self.get_name(), "ZWCAD COM dependencies are not installed", status="unavailable")

        # Integration point:
        # Import existing HS-CAD adapter here and call its read-only scan methods.
        # Return unavailable rather than risking unintended DWG mutation.
        return FileizedDrawingRecord.failed(
            path,
            self.get_name(),
            "ZWCAD COM fileizer integration is not wired yet; reuse existing adapter read-only scan here.",
            status="unavailable",
        )
