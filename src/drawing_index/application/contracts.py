from __future__ import annotations

from typing import Protocol, Sequence

from src.drawing_index.domain.models import FileIndexSummary, IndexRunSummary


class RunSummarySink(Protocol):
    """Destination for privacy-conscious run telemetry."""

    def publish(
        self,
        run: IndexRunSummary,
        files: Sequence[FileIndexSummary],
    ) -> dict:
        ...


class NullRunSummarySink:
    def publish(
        self,
        run: IndexRunSummary,
        files: Sequence[FileIndexSummary],
    ) -> dict:
        return {
            "backend": "none",
            "published": False,
            "run_id": run.run_id,
            "file_count": len(files),
        }
