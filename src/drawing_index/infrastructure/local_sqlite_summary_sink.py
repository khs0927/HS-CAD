from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from src.drawing_index.application.contracts import RunSummarySink
from src.drawing_index.domain.models import FileIndexSummary, IndexRunSummary


_SCHEMA = """
CREATE TABLE IF NOT EXISTS drawing_index_runs (
  run_id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT NOT NULL,
  status TEXT NOT NULL,
  file_count INTEGER NOT NULL,
  complete_count INTEGER NOT NULL,
  review_count INTEGER NOT NULL,
  failed_count INTEGER NOT NULL,
  unavailable_count INTEGER NOT NULL,
  total_entities INTEGER NOT NULL,
  total_text_occurrences INTEGER NOT NULL,
  metadata_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drawing_index_files (
  run_id TEXT NOT NULL,
  file_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  extension TEXT NOT NULL,
  status TEXT NOT NULL,
  engine TEXT NOT NULL,
  complete INTEGER NOT NULL,
  entity_count INTEGER NOT NULL,
  text_occurrence_count INTEGER NOT NULL,
  layout_count INTEGER NOT NULL,
  xref_count INTEGER NOT NULL,
  warning_count INTEGER NOT NULL,
  error_count INTEGER NOT NULL,
  requires_ocr_count INTEGER NOT NULL,
  unsupported_proxy_count INTEGER NOT NULL,
  unresolved_xref_count INTEGER NOT NULL,
  blockers_json TEXT NOT NULL,
  extraction_report_json TEXT NOT NULL,
  PRIMARY KEY (run_id, file_id),
  FOREIGN KEY (run_id) REFERENCES drawing_index_runs(run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS drawing_index_runs_completed_idx
  ON drawing_index_runs(completed_at DESC);
CREATE INDEX IF NOT EXISTS drawing_index_files_review_idx
  ON drawing_index_files(run_id, complete, status);
"""


class LocalSQLiteRunSummarySink(RunSummarySink):
    """Persist run history locally with no account, API key, or network access."""

    backend = "local_sqlite"

    def __init__(self, sqlite_path: str | Path) -> None:
        self.sqlite_path = Path(sqlite_path)

    def publish(
        self,
        run: IndexRunSummary,
        files: Sequence[FileIndexSummary],
    ) -> dict[str, Any]:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript(_SCHEMA)
            conn.execute(
                """
                INSERT INTO drawing_index_runs(
                  run_id, workspace_id, started_at, completed_at, status,
                  file_count, complete_count, review_count, failed_count,
                  unavailable_count, total_entities, total_text_occurrences,
                  metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                  workspace_id=excluded.workspace_id,
                  started_at=excluded.started_at,
                  completed_at=excluded.completed_at,
                  status=excluded.status,
                  file_count=excluded.file_count,
                  complete_count=excluded.complete_count,
                  review_count=excluded.review_count,
                  failed_count=excluded.failed_count,
                  unavailable_count=excluded.unavailable_count,
                  total_entities=excluded.total_entities,
                  total_text_occurrences=excluded.total_text_occurrences,
                  metadata_json=excluded.metadata_json
                """,
                (
                    run.run_id,
                    run.workspace_id,
                    run.started_at,
                    run.completed_at,
                    run.status,
                    run.file_count,
                    run.complete_count,
                    run.review_count,
                    run.failed_count,
                    run.unavailable_count,
                    run.total_entities,
                    run.total_text_occurrences,
                    json.dumps(run.metadata, ensure_ascii=False),
                ),
            )
            conn.execute("DELETE FROM drawing_index_files WHERE run_id = ?", (run.run_id,))
            conn.executemany(
                """
                INSERT INTO drawing_index_files(
                  run_id, file_id, relative_path, extension, status, engine,
                  complete, entity_count, text_occurrence_count, layout_count,
                  xref_count, warning_count, error_count, requires_ocr_count,
                  unsupported_proxy_count, unresolved_xref_count, blockers_json,
                  extraction_report_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [self._file_row(run.run_id, item) for item in files],
            )
        return {
            "backend": self.backend,
            "published": True,
            "network_used": False,
            "run_id": run.run_id,
            "file_count": len(files),
            "sqlite": str(self.sqlite_path),
        }

    @staticmethod
    def _file_row(run_id: str, item: FileIndexSummary) -> tuple[Any, ...]:
        return (
            run_id,
            item.file_id,
            item.relative_path,
            item.extension,
            item.status,
            item.engine,
            int(item.complete),
            item.entity_count,
            item.text_occurrence_count,
            item.layout_count,
            item.xref_count,
            item.warning_count,
            item.error_count,
            item.requires_ocr_count,
            item.unsupported_proxy_count,
            item.unresolved_xref_count,
            json.dumps(list(item.blockers), ensure_ascii=False),
            json.dumps(item.extraction_report, ensure_ascii=False),
        )
