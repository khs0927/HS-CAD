from __future__ import annotations

from pathlib import Path


def load_pdf_pages(path: str | Path, out_dir: str | Path | None = None) -> dict:
    pdf_path = Path(path)
    warnings = ["optional_dependency_missing: PDF rasterization backend is not installed"]
    return {"pdf_path": str(pdf_path), "pages": [], "warnings": warnings}

