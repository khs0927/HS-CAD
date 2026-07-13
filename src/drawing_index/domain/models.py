from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.corpus.schema import FileizedDrawingRecord

PUBLIC_REPORT_FIELDS = frozenset(
    {
        "schema_version",
        "scanner",
        "entity_count",
        "text_occurrence_count",
        "layout_count",
        "block_definition_entity_count",
        "xref_count",
        "requires_ocr_count",
        "unsupported_proxy_count",
        "unresolved_xref_count",
        "missing_layout_count",
        "entity_failure_count",
        "warning_count",
        "error_count",
        "complete",
        "coverage",
        "blockers",
        "attempt_count",
        "selected_engine",
        "fallback_used",
        "fileizer_attempts",
    }
)


def public_extraction_report(report: dict[str, Any]) -> dict[str, Any]:
    """Return metrics safe for the optional remote summary control plane."""

    public = {key: value for key, value in report.items() if key in PUBLIC_REPORT_FIELDS}
    coverage = public.get("coverage")
    if isinstance(coverage, dict):
        public["coverage"] = {
            str(key): bool(value) for key, value in coverage.items()
        }
    attempts = public.get("fileizer_attempts")
    if isinstance(attempts, list):
        public["fileizer_attempts"] = [
            {
                key: attempt[key]
                for key in ("engine", "status", "complete", "quality_score")
                if key in attempt
            }
            for attempt in attempts
            if isinstance(attempt, dict)
        ]
    return public


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class FileIndexSummary:
    """Privacy-conscious summary of one indexed drawing.

    Absolute source paths and full extracted text are intentionally excluded so
    this object can be sent to an optional remote monitoring service.
    """

    file_id: str
    relative_path: str
    extension: str
    status: str
    engine: str
    complete: bool
    entity_count: int
    text_occurrence_count: int
    layout_count: int
    xref_count: int
    warning_count: int
    error_count: int
    requires_ocr_count: int
    unsupported_proxy_count: int
    unresolved_xref_count: int
    blockers: tuple[str, ...] = ()
    extraction_report: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_record(cls, record: FileizedDrawingRecord) -> FileIndexSummary:
        report = dict(record.extraction_report or {})
        blockers = tuple(str(item) for item in report.get("blockers") or [])
        return cls(
            file_id=record.file_id,
            relative_path=record.relative_path,
            extension=record.extension,
            status=record.status,
            engine=record.engine,
            complete=bool(report.get("complete")),
            entity_count=int(report.get("entity_count", len(record.entities)) or 0),
            text_occurrence_count=int(
                report.get("text_occurrence_count", len(record.texts)) or 0
            ),
            layout_count=int(report.get("layout_count", len(record.layouts)) or 0),
            xref_count=int(report.get("xref_count", len(record.xrefs)) or 0),
            warning_count=int(report.get("warning_count", len(record.warnings)) or 0),
            error_count=len(record.errors),
            requires_ocr_count=int(report.get("requires_ocr_count") or 0),
            unsupported_proxy_count=int(report.get("unsupported_proxy_count") or 0),
            unresolved_xref_count=int(report.get("unresolved_xref_count") or 0),
            blockers=blockers,
            extraction_report=public_extraction_report(report),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        return payload


@dataclass(frozen=True)
class IndexRunSummary:
    run_id: str
    workspace_id: str
    started_at: str
    completed_at: str
    status: str
    file_count: int
    complete_count: int
    review_count: int
    failed_count: int
    unavailable_count: int
    total_entities: int
    total_text_occurrences: int
    files: tuple[FileIndexSummary, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        *,
        workspace_id: str,
        started_at: str,
        files: Iterable[FileIndexSummary],
        metadata: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> IndexRunSummary:
        rows = tuple(files)
        failed = sum(1 for item in rows if item.status == "failed")
        unavailable = sum(1 for item in rows if item.status == "unavailable")
        complete = sum(1 for item in rows if item.status == "ok" and item.complete)
        review = len(rows) - complete
        if failed:
            status = "failed"
        elif review:
            status = "review"
        else:
            status = "complete"
        return cls(
            run_id=run_id or str(uuid4()),
            workspace_id=workspace_id,
            started_at=started_at,
            completed_at=utc_now_iso(),
            status=status,
            file_count=len(rows),
            complete_count=complete,
            review_count=review,
            failed_count=failed,
            unavailable_count=unavailable,
            total_entities=sum(item.entity_count for item in rows),
            total_text_occurrences=sum(item.text_occurrence_count for item in rows),
            files=rows,
            metadata=dict(metadata or {}),
        )

    def to_dict(self, *, include_files: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        payload["files"] = [item.to_dict() for item in self.files] if include_files else []
        return payload
