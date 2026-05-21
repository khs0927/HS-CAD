"""Drawing fileizers convert CAD/document files into structured records.

This package is intentionally read-only: it never modifies source drawings.
"""

from .models import FileizedDrawingRecord, FileizedEntity
from .fileizer_registry import FileizerRegistry

__all__ = ["FileizedDrawingRecord", "FileizedEntity", "FileizerRegistry"]
