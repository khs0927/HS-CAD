from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    file_id TEXT PRIMARY KEY,
    source_path TEXT,
    relative_path TEXT,
    extension TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS fileized_records (
    file_id TEXT PRIMARY KEY,
    json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT,
    material_name TEXT,
    normalized_name TEXT,
    category TEXT,
    context_text TEXT,
    confidence REAL
);

CREATE TABLE IF NOT EXISTS specifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT,
    raw_text TEXT,
    normalized_value TEXT,
    unit TEXT,
    spec_type TEXT,
    context_text TEXT,
    confidence REAL
);

CREATE TABLE IF NOT EXISTS dimensions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT,
    raw_text TEXT,
    value TEXT,
    unit TEXT,
    role TEXT,
    context_text TEXT,
    confidence REAL
);

CREATE TABLE IF NOT EXISTS situations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT,
    tag TEXT,
    evidence_text TEXT,
    matched_keywords TEXT,
    confidence REAL
);

CREATE TABLE IF NOT EXISTS detail_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT,
    pattern_name TEXT,
    situation_tag TEXT,
    json TEXT,
    confidence REAL
);

CREATE TABLE IF NOT EXISTS architectural_lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    situation_tag TEXT,
    lesson TEXT,
    confidence REAL,
    evidence_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS processing_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT,
    stage TEXT,
    message TEXT
);
"""


class KnowledgeStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _init(self) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.executescript(SCHEMA)
            try:
                con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS texts_fts USING fts5(file_id, text)")
            except sqlite3.OperationalError:
                # FTS5 may not be enabled in all SQLite builds.
                pass

    def upsert_fileized_record(self, record: Any) -> None:
        file_id = getattr(record, "file_id", record.get("file_id"))
        json_text = record.model_dump_json() if hasattr(record, "model_dump_json") else json.dumps(record, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR REPLACE INTO fileized_records(file_id, json) VALUES (?, ?)", (file_id, json_text))

    def insert_materials(self, file_id: str, materials: list[Any]) -> None:
        with sqlite3.connect(self.db_path) as con:
            for m in materials:
                con.execute(
                    """
                    INSERT INTO materials(file_id, material_name, normalized_name, category, context_text, confidence)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        file_id,
                        getattr(m, "material_name", ""),
                        getattr(m, "normalized_name", ""),
                        getattr(m, "category", ""),
                        getattr(m, "context_text", ""),
                        getattr(m, "confidence", 0.0),
                    ),
                )

    def insert_specifications(self, file_id: str, specs: list[Any]) -> None:
        with sqlite3.connect(self.db_path) as con:
            for s in specs:
                con.execute(
                    """
                    INSERT INTO specifications(file_id, raw_text, normalized_value, unit, spec_type, context_text, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        file_id,
                        getattr(s, "raw_text", ""),
                        getattr(s, "normalized_value", ""),
                        getattr(s, "unit", None),
                        getattr(s, "spec_type", ""),
                        getattr(s, "context_text", ""),
                        getattr(s, "confidence", 0.0),
                    ),
                )

    def insert_dimensions(self, file_id: str, dimensions: list[Any]) -> None:
        with sqlite3.connect(self.db_path) as con:
            for d in dimensions:
                con.execute(
                    """
                    INSERT INTO dimensions(file_id, raw_text, value, unit, role, context_text, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        file_id,
                        getattr(d, "raw_text", ""),
                        getattr(d, "value", ""),
                        getattr(d, "unit", None),
                        getattr(d, "role", ""),
                        getattr(d, "context_text", ""),
                        getattr(d, "confidence", 0.0),
                    ),
                )

    def insert_situations(self, file_id: str, situations: list[Any]) -> None:
        with sqlite3.connect(self.db_path) as con:
            for s in situations:
                con.execute(
                    """
                    INSERT INTO situations(file_id, tag, evidence_text, matched_keywords, confidence)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        file_id,
                        getattr(s, "tag", ""),
                        getattr(s, "evidence_text", ""),
                        json.dumps(getattr(s, "matched_keywords", []), ensure_ascii=False),
                        getattr(s, "confidence", 0.0),
                    ),
                )

    def query_keyword(self, query: str, limit: int = 20) -> dict[str, list[dict[str, Any]]]:
        pattern = f"%{query}%"
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            return {
                "materials": [dict(r) for r in con.execute("SELECT * FROM materials WHERE material_name LIKE ? OR context_text LIKE ? LIMIT ?", (pattern, pattern, limit))],
                "specifications": [dict(r) for r in con.execute("SELECT * FROM specifications WHERE raw_text LIKE ? OR context_text LIKE ? LIMIT ?", (pattern, pattern, limit))],
                "situations": [dict(r) for r in con.execute("SELECT * FROM situations WHERE tag LIKE ? OR evidence_text LIKE ? LIMIT ?", (pattern, pattern, limit))],
            }
