from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from src.corpus.schema import FileizedDrawingRecord


@dataclass(frozen=True)
class CompletenessResult:
    complete: bool
    blockers: tuple[str, ...]
    review_reasons: tuple[dict[str, Any], ...]


class CompletenessPolicy:
    """Single source of truth for deciding whether extraction is complete.

    Fileizers report facts. This policy converts those facts into a stable
    decision so ZWCAD, DXF, PDF, and future IFC extractors use the same rules.
    """

    COUNT_BLOCKERS = (
        "requires_ocr_count",
        "unsupported_proxy_count",
        "unresolved_xref_count",
        "missing_layout_count",
        "entity_failure_count",
    )

    def evaluate(self, record: FileizedDrawingRecord) -> CompletenessResult:
        report = dict(record.extraction_report or {})
        blockers: list[str] = []
        reasons: list[dict[str, Any]] = []

        if record.status != "ok":
            blockers.append(f"status={record.status}")

        for key in self.COUNT_BLOCKERS:
            value = self._int(report.get(key))
            if value:
                blockers.append(f"{key}={value}")

        if report.get("opened_read_only") is False:
            blockers.append("opened_read_only=false")

        coverage = report.get("coverage") or {}
        if isinstance(coverage, dict):
            for capability, covered in sorted(coverage.items()):
                if covered is False:
                    blockers.append(f"coverage:{capability}=false")

        for warning in self._iter_dicts(record.warnings):
            warning_type = str(warning.get("type") or "warning")
            reasons.append(warning)
            blockers.append(f"warning:{warning_type}")

        for error in self._iter_dicts(record.errors):
            error_type = str(error.get("type") or "error")
            reasons.append(error)
            blockers.append(f"error:{error_type}")

        # Respect an extractor's explicit negative assertion even when an older
        # adapter did not yet provide a structured reason. This prevents a
        # policy upgrade from silently turning an unknown omission into PASS.
        if report.get("complete") is False and not blockers:
            blockers.append("extractor_reported_incomplete")

        blockers = self._unique(blockers)
        return CompletenessResult(
            complete=record.status == "ok" and not blockers,
            blockers=tuple(blockers),
            review_reasons=tuple(reasons),
        )

    def apply(self, record: FileizedDrawingRecord) -> CompletenessResult:
        result = self.evaluate(record)
        report = dict(record.extraction_report or {})
        report["complete"] = result.complete
        report["blockers"] = list(result.blockers)
        report["review_reason_count"] = len(result.review_reasons)
        record.extraction_report = report
        return result

    @staticmethod
    def quality_score(record: FileizedDrawingRecord) -> tuple[int, int, int, int, int]:
        """Return a deterministic score used to choose among fallback engines."""

        report = record.extraction_report or {}
        complete = 1 if bool(report.get("complete")) else 0
        ok = 1 if record.status == "ok" else 0
        text_count = int(report.get("text_occurrence_count", len(record.texts)) or 0)
        layout_count = int(report.get("layout_count", len(record.layouts)) or 0)
        penalty = len(record.warnings) + (10 * len(record.errors))
        return (ok, complete, text_count, layout_count, -penalty)

    @staticmethod
    def _int(value: object) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _iter_dicts(values: Iterable[object]) -> Iterable[dict[str, Any]]:
        for value in values:
            if isinstance(value, dict):
                yield value
            else:
                yield {"type": "message", "message": str(value)}

    @staticmethod
    def _unique(values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            out.append(value)
        return out
