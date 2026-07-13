from __future__ import annotations

from pathlib import Path

from src.corpus.schema import FileizedDrawingRecord
from src.drawing_index.application.fileizer_registry import FileizerRegistry
from src.drawing_index.domain.completeness import CompletenessPolicy
from src.drawing_index.domain.models import FileIndexSummary, IndexRunSummary
from src.drawing_index.infrastructure.supabase_summary_sink import (
    SupabaseRunSummarySink,
    SupabaseSummarySettings,
)
from src.fileizers.base import DrawingFileizer, FileizedRecordWriter


def _record(
    engine: str,
    *,
    complete: bool,
    texts: int = 0,
    warnings: list[dict] | None = None,
) -> FileizedDrawingRecord:
    rows = [
        {
            "occurrence_id": f"text-{index}",
            "plain_text": f"T{index}",
            "normalized_text": f"t{index}",
        }
        for index in range(texts)
    ]
    return FileizedDrawingRecord(
        file_id="f1",
        source_path="C:/private/source.dwg",
        relative_path="plans/source.dwg",
        extension=".dwg",
        status="ok",
        engine=engine,
        texts=rows,
        extraction_report={
            "complete": complete,
            "text_occurrence_count": texts,
            "layout_count": 1,
            "coverage": {"model_space": True},
        },
        warnings=list(warnings or []),
    )


class _FakeFileizer(DrawingFileizer):
    supported_extensions = (".dwg",)

    def __init__(self, engine: str, record: FileizedDrawingRecord):
        self.engine_name = engine
        self.record = record
        self.calls = 0

    def fileize(self, path, *, file_id, relative_path):
        self.calls += 1
        self.record.file_id = file_id
        self.record.source_path = str(path)
        self.record.relative_path = str(relative_path)
        return self.record


def test_completeness_policy_never_accepts_warning_as_complete() -> None:
    record = _record(
        "native",
        complete=True,
        warnings=[{"type": "layout_block_unavailable"}],
    )
    result = CompletenessPolicy().apply(record)
    assert result.complete is False
    assert "warning:layout_block_unavailable" in result.blockers
    assert record.extraction_report["complete"] is False


def test_completeness_policy_requires_explicit_positive_assertion() -> None:
    record = _record("legacy", complete=True)
    record.extraction_report.pop("complete")
    result = CompletenessPolicy().apply(record)
    assert result.complete is False
    assert "complete_assertion_missing" in result.blockers


def test_registry_continues_after_incomplete_result_and_selects_complete_fallback() -> None:
    native = _FakeFileizer(
        "native",
        _record(
            "native",
            complete=False,
            texts=20,
            warnings=[{"type": "unsupported_proxy"}],
        ),
    )
    fallback = _FakeFileizer("fallback", _record("fallback", complete=True, texts=10))
    registry = FileizerRegistry([native, fallback])

    result = registry.fileize(
        Path("source.dwg"),
        file_id="f1",
        relative_path="source.dwg",
    )

    assert native.calls == 1
    assert fallback.calls == 1
    assert result.engine == "fallback"
    assert result.extraction_report["complete"] is True
    assert result.extraction_report["fallback_used"] is True
    assert result.extraction_report["attempt_count"] == 2


def test_registry_stops_after_first_complete_result() -> None:
    native = _FakeFileizer("native", _record("native", complete=True, texts=4))
    fallback = _FakeFileizer("fallback", _record("fallback", complete=True, texts=9))
    result = FileizerRegistry([native, fallback]).fileize(
        "source.dwg",
        file_id="f1",
        relative_path="source.dwg",
    )
    assert result.engine == "native"
    assert native.calls == 1
    assert fallback.calls == 0


def test_record_writer_places_incomplete_ok_record_in_review_queue(tmp_path: Path) -> None:
    record = _record(
        "native",
        complete=False,
        warnings=[{"type": "unsupported_proxy"}],
    )
    CompletenessPolicy().apply(record)
    paths = FileizedRecordWriter(tmp_path).write(record)

    assert "review" in paths
    assert Path(paths["review"]).exists()
    assert "failure" not in paths
    markdown = Path(paths["markdown"]).read_text(encoding="utf-8")
    assert "Review blockers" in markdown
    assert "warning:unsupported_proxy" in markdown


class _Response:
    status_code = 201
    text = ""


class _Session:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _Response()


def test_supabase_sink_publishes_summary_without_private_source_path_or_text() -> None:
    record = _record("native", complete=True, texts=2)
    record.extraction_report.update(
        {
            "private_text": "DO_NOT_UPLOAD_DRAWING_TEXT",
            "absolute_path": "C:/private/source.dwg",
            "fileizer_attempts": [
                {
                    "engine": "native",
                    "status": "ok",
                    "complete": True,
                    "reason": "C:/private/source.dwg contains DO_NOT_UPLOAD_DRAWING_TEXT",
                    "quality_score": [1, 1, 2, 1, 0],
                }
            ],
        }
    )
    file_summary = FileIndexSummary.from_record(record)
    run = IndexRunSummary.build(
        workspace_id="workspace-test",
        started_at="2026-07-13T00:00:00+00:00",
        files=[file_summary],
        run_id="00000000-0000-0000-0000-000000000001",
    )
    session = _Session()
    sink = SupabaseRunSummarySink(
        SupabaseSummarySettings(
            url="https://example.supabase.co",
            service_role_key="x" * 40,
        ),
        session=session,
    )

    result = sink.publish(run, [file_summary])

    assert result["published"] is True
    assert len(session.calls) == 2
    payload_text = repr([kwargs["json"] for _, kwargs in session.calls])
    assert "C:/private/source.dwg" not in payload_text
    assert "DO_NOT_UPLOAD_DRAWING_TEXT" not in payload_text
    assert "plans/source.dwg" in payload_text
