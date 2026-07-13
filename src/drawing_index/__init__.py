"""HS-CAD drawing index application package.

This package contains the orchestration and policy layer for the drawing corpus.
CAD-specific extraction stays in ``src.adapters`` and persistence stays in
``src.corpus`` so each concern can be tested and replaced independently.
"""

from src.drawing_index.application.fileizer_registry import FileizerRegistry
from src.drawing_index.domain.completeness import CompletenessPolicy
from src.drawing_index.domain.models import FileIndexSummary, IndexRunSummary

__all__ = [
    "CompletenessPolicy",
    "FileIndexSummary",
    "FileizerRegistry",
    "IndexRunSummary",
]
