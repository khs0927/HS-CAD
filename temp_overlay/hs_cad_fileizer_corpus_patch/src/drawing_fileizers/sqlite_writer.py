from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import FileizedDrawingRecord


def upsert_fileized_record(db_path: Path, record: FileizedDrawingRecord) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS fileized_records (
                file_id TEXT PRIMARY KEY,
                source_path TEXT,
                extension TEXT,
                fileizer TEXT,
                status TEXT,
                json TEXT
            )
            """
        )
        con.execute(
            """
            INSERT OR REPLACE INTO fileized_records
            (file_id, source_path, extension, fileizer, status, json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (record.file_id, record.source_path, record.extension, record.fileizer, record.status, record.model_dump_json()),
        )
