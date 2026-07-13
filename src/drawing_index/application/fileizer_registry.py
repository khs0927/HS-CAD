from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from src.corpus.schema import FileizedDrawingRecord
from src.drawing_index.domain.completeness import CompletenessPolicy
from src.fileizers.base import DrawingFileizer


@dataclass(frozen=True)
class FileizerAttempt:
    engine: str
    status: str
    complete: bool
    reason: str
    quality_score: tuple[int, int, int, int, int]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["quality_score"] = list(self.quality_score)
        return payload


class FileizerRegistry:
    """Ordered extractor registry with completeness-aware fallback selection.

    A successful file open is not enough. If the first matching extractor
    returns an incomplete record, the registry continues to the next available
    extractor and keeps the highest-quality result.
    """

    def __init__(
        self,
        fileizers: Iterable[DrawingFileizer] | None = None,
        *,
        policy: CompletenessPolicy | None = None,
    ) -> None:
        self._fileizers: list[DrawingFileizer] = list(fileizers or [])
        self.policy = policy or CompletenessPolicy()

    @property
    def fileizers(self) -> tuple[DrawingFileizer, ...]:
        return tuple(self._fileizers)

    def register(self, fileizer: DrawingFileizer, *, first: bool = False) -> None:
        if any(item.engine_name == fileizer.engine_name for item in self._fileizers):
            raise ValueError(f"fileizer already registered: {fileizer.engine_name}")
        if first:
            self._fileizers.insert(0, fileizer)
        else:
            self._fileizers.append(fileizer)

    def fileize(
        self,
        path: str | Path,
        *,
        file_id: str,
        relative_path: str | Path,
    ) -> FileizedDrawingRecord:
        source = Path(path)
        attempts: list[FileizerAttempt] = []
        best_record: FileizedDrawingRecord | None = None
        best_score: tuple[int, int, int, int, int] | None = None
        matched = False

        for fileizer in self._fileizers:
            if not fileizer.supports(source):
                continue
            matched = True
            record = fileizer.fileize(
                source,
                file_id=file_id,
                relative_path=relative_path,
            )
            result = self.policy.apply(record)
            score = self.policy.quality_score(record)
            attempts.append(
                FileizerAttempt(
                    engine=fileizer.engine_name,
                    status=record.status,
                    complete=result.complete,
                    reason=self._record_reason(record),
                    quality_score=score,
                )
            )

            if best_score is None or score > best_score:
                best_record = record
                best_score = score

            if result.complete:
                best_record = record
                break

        if not matched:
            record = FileizedDrawingRecord.unavailable(
                file_id=file_id,
                source_path=source,
                relative_path=relative_path,
                extension=source.suffix,
                engine="none",
                reason=f"No fileizer registered for extension {source.suffix.lower()}",
            )
            self.policy.apply(record)
            return record

        assert best_record is not None
        report = dict(best_record.extraction_report or {})
        report["fileizer_attempts"] = [item.to_dict() for item in attempts]
        report["attempt_count"] = len(attempts)
        report["selected_engine"] = best_record.engine
        report["fallback_used"] = bool(
            attempts and attempts[0].engine != best_record.engine
        )
        best_record.extraction_report = report
        self.policy.apply(best_record)
        return best_record

    @staticmethod
    def _record_reason(record: FileizedDrawingRecord) -> str:
        if record.errors:
            first = record.errors[0]
            return str(first.get("reason") or first.get("error") or first)
        if record.warnings:
            first = record.warnings[0]
            return str(first.get("reason") or first.get("error") or first)
        report = record.extraction_report or {}
        return str(report.get("failure_reason") or "")

