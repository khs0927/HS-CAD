from __future__ import annotations

from src.corpus.schema import FileizedDrawingRecord
from src.drawing_index.domain.models import FileIndexSummary, IndexRunSummary
from src.drawing_index.infrastructure.supabase_summary_sink import SupabaseRunSummarySink


def test_remote_summary_hashes_operator_and_file_identifiers() -> None:
    record = FileizedDrawingRecord(
        file_id="path-derived-local-id",
        source_path="C:/clients/secret-project/source.dwg",
        relative_path="clients/secret-project/source.dwg",
        extension=".dwg",
        status="ok",
        engine="ezdxf_complete",
        extraction_report={
            "complete": True,
            "entity_count": 10,
            "text_occurrence_count": 2,
            "layout_count": 1,
        },
    )
    item = FileIndexSummary.from_record(record)
    run = IndexRunSummary.build(
        workspace_id="client-office-secret-label",
        started_at="2026-07-16T00:00:00+00:00",
        files=[item],
        run_id="00000000-0000-0000-0000-000000000003",
    )

    run_row = SupabaseRunSummarySink._run_row(run)
    file_row = SupabaseRunSummarySink._file_row(run.run_id, item)
    serialized = repr([run_row, file_row])

    assert run_row["workspace_id"].startswith("sha256:")
    assert file_row["file_id"].startswith("sha256:")
    assert file_row["relative_path"] == SupabaseRunSummarySink.REDACTED_PATH
    assert "client-office-secret-label" not in serialized
    assert "path-derived-local-id" not in serialized
    assert "clients/secret-project/source.dwg" not in serialized


def test_remote_file_tokens_are_scoped_to_each_run() -> None:
    record = FileizedDrawingRecord(
        file_id="same-local-id",
        source_path="C:/private/source.dwg",
        relative_path="source.dwg",
        extension=".dwg",
        status="ok",
        engine="test",
        extraction_report={"complete": True},
    )
    item = FileIndexSummary.from_record(record)

    first = SupabaseRunSummarySink._file_row("run-a", item)["file_id"]
    second = SupabaseRunSummarySink._file_row("run-b", item)["file_id"]

    assert first != second
