from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

from src.corpus.schema import FileizedDrawingRecord
from src.drawing_index.domain.models import FileIndexSummary, IndexRunSummary
from src.drawing_index.infrastructure.local_sqlite_summary_sink import (
    LocalSQLiteRunSummarySink,
)


def _summary_record() -> FileizedDrawingRecord:
    return FileizedDrawingRecord(
        file_id="free-file",
        source_path="C:/private/source.dwg",
        relative_path="plans/source.dwg",
        extension=".dwg",
        status="ok",
        engine="ezdxf_complete",
        texts=[
            {
                "occurrence_id": "one",
                "plain_text": "방화문",
                "normalized_text": "방화문",
            }
        ],
        extraction_report={
            "complete": True,
            "entity_count": 10,
            "text_occurrence_count": 1,
            "layout_count": 1,
            "xref_count": 0,
            "coverage": {"model_space": True},
        },
    )


def test_local_sqlite_sink_works_without_network_or_keys(tmp_path: Path) -> None:
    item = FileIndexSummary.from_record(_summary_record())
    run = IndexRunSummary.build(
        workspace_id="local-test",
        started_at="2026-07-13T00:00:00+00:00",
        files=[item],
        run_id="00000000-0000-0000-0000-000000000002",
    )
    db_path = tmp_path / "history.sqlite"

    result = LocalSQLiteRunSummarySink(db_path).publish(run, [item])

    assert result["published"] is True
    assert result["network_used"] is False
    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        run_row = conn.execute(
            "SELECT status, file_count, total_text_occurrences FROM drawing_index_runs"
        ).fetchone()
        file_row = conn.execute(
            "SELECT relative_path, complete, text_occurrence_count FROM drawing_index_files"
        ).fetchone()
    assert run_row == ("complete", 1, 1)
    assert file_row == ("plans/source.dwg", 1, 1)


def test_free_only_validator_accepts_repository_runtime() -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "validate_free_only.py"
    spec = importlib.util.spec_from_file_location("validate_free_only", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    result = module.validate(root)

    assert result["valid"] is True, result["issues"]
    assert result["forbidden_runtime_dependencies"] == []
    assert (root / "config" / "free-only.env.example").exists()
    assert (
        root
        / "src"
        / "drawing_index"
        / "infrastructure"
        / "local_sqlite_summary_sink.py"
    ).exists()
