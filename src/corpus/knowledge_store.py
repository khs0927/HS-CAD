from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable


class KnowledgeStore:
    """HS-CAD Corpus용 SQLite 지식 저장소.

    외부 도면 스타일을 표준화하지 않고, 일반 건축 지식과 근거를 저장한다.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.init_schema()

    def close(self) -> None:
        self.conn.close()

    def init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS files (
                file_id TEXT PRIMARY KEY,
                source_path TEXT,
                relative_path TEXT,
                extension TEXT,
                status TEXT,
                metadata_json TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS fileized_records (
                file_id TEXT PRIMARY KEY,
                json_path TEXT,
                fileizer TEXT,
                fileizer_version TEXT,
                status TEXT,
                raw_json TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS texts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT,
                text TEXT,
                source TEXT,
                context TEXT
            );

            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT,
                name TEXT,
                normalized_name TEXT,
                category TEXT,
                context TEXT,
                confidence REAL
            );

            CREATE TABLE IF NOT EXISTS specifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT,
                raw_text TEXT,
                normalized_value TEXT,
                unit TEXT,
                spec_type TEXT,
                context TEXT,
                confidence REAL
            );

            CREATE TABLE IF NOT EXISTS dimensions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT,
                raw_text TEXT,
                role TEXT,
                value TEXT,
                unit TEXT,
                context TEXT,
                confidence REAL
            );

            CREATE TABLE IF NOT EXISTS situations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT,
                tag TEXT,
                evidence TEXT,
                confidence REAL
            );

            CREATE TABLE IF NOT EXISTS canonical_elements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT,
                canonical_element TEXT,
                evidence TEXT,
                source_kind TEXT,
                confidence REAL
            );

            CREATE TABLE IF NOT EXISTS detail_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT,
                pattern_name TEXT,
                situation_tag TEXT,
                elements_json TEXT,
                materials_json TEXT,
                dimensions_json TEXT,
                notes_json TEXT,
                confidence REAL
            );

            CREATE TABLE IF NOT EXISTS architectural_lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                situation_tag TEXT,
                lesson TEXT,
                evidence_count INTEGER,
                confidence REAL
            );

            CREATE TABLE IF NOT EXISTS company_output_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT,
                situation_tag TEXT,
                recommendation_json TEXT,
                confidence REAL
            );

            CREATE TABLE IF NOT EXISTS processing_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT,
                stage TEXT,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self._try_create_fts()
        self.conn.commit()

    def _try_create_fts(self) -> None:
        cur = self.conn.cursor()
        try:
            cur.execute("CREATE VIRTUAL TABLE IF NOT EXISTS texts_fts USING fts5(file_id, text, context)")
            cur.execute("CREATE VIRTUAL TABLE IF NOT EXISTS lessons_fts USING fts5(situation_tag, lesson)")
        except sqlite3.OperationalError:
            # FTS5가 없는 Python 빌드도 있으므로 LIKE fallback으로 동작한다.
            pass

    def upsert_fileized_record(self, record: dict[str, Any], json_path: str | None = None) -> None:
        file_id = str(record.get("file_id") or record.get("id") or "")
        if not file_id:
            raise ValueError("fileized record requires file_id")

        source_path = str(record.get("source_path") or "")
        rel = str(record.get("relative_path") or "")
        ext = str(record.get("extension") or Path(source_path).suffix)
        status = str(record.get("status") or "unknown")
        metadata_json = json.dumps(record.get("metadata") or {}, ensure_ascii=False)
        raw_json = json.dumps(record, ensure_ascii=False)

        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO files(file_id, source_path, relative_path, extension, status, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_id) DO UPDATE SET
                source_path=excluded.source_path,
                relative_path=excluded.relative_path,
                extension=excluded.extension,
                status=excluded.status,
                metadata_json=excluded.metadata_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (file_id, source_path, rel, ext, status, metadata_json),
        )
        cur.execute(
            """
            INSERT INTO fileized_records(file_id, json_path, fileizer, fileizer_version, status, raw_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_id) DO UPDATE SET
                json_path=excluded.json_path,
                fileizer=excluded.fileizer,
                fileizer_version=excluded.fileizer_version,
                status=excluded.status,
                raw_json=excluded.raw_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                file_id,
                json_path or "",
                str(record.get("fileizer") or ""),
                str(record.get("fileizer_version") or ""),
                status,
                raw_json,
            ),
        )
        self.conn.commit()

    def add_texts(self, file_id: str, texts: Iterable[str], source: str = "fileized") -> None:
        cur = self.conn.cursor()
        rows = [(file_id, str(t), source, str(t)[:240]) for t in texts if str(t).strip()]
        cur.executemany("INSERT INTO texts(file_id, text, source, context) VALUES (?, ?, ?, ?)", rows)
        # Insert into the FTS virtual table (which expects only file_id, text, context)
        fts_rows = [(r[0], r[1], r[3]) for r in rows]
        try:
            cur.executemany("INSERT INTO texts_fts(file_id, text, context) VALUES (?, ?, ?)", fts_rows)
        except sqlite3.OperationalError:
            pass
        self.conn.commit()

    def add_materials(self, file_id: str, mentions: Iterable[Any]) -> None:
        rows = []
        for m in mentions:
            rows.append(
                (
                    file_id,
                    _get(m, "material_name", _get(m, "name", "")),
                    _get(m, "normalized_name", ""),
                    _get(m, "category", ""),
                    _get(m, "context_text", _get(m, "context", "")),
                    float(_get(m, "confidence", 0.0)),
                )
            )
        self.conn.executemany(
            "INSERT INTO materials(file_id, name, normalized_name, category, context, confidence) VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        self.conn.commit()

    def add_specifications(self, file_id: str, mentions: Iterable[Any]) -> None:
        rows = [
            (
                file_id,
                _get(m, "raw_text", ""),
                _get(m, "normalized_value", ""),
                _get(m, "unit", ""),
                _get(m, "spec_type", ""),
                _get(m, "context_text", _get(m, "context", "")),
                float(_get(m, "confidence", 0.0)),
            )
            for m in mentions
        ]
        self.conn.executemany(
            "INSERT INTO specifications(file_id, raw_text, normalized_value, unit, spec_type, context, confidence) VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        self.conn.commit()

    def add_dimensions(self, file_id: str, mentions: Iterable[Any]) -> None:
        rows = [
            (
                file_id,
                _get(m, "raw_text", ""),
                _get(m, "role", ""),
                _get(m, "value", ""),
                _get(m, "unit", ""),
                _get(m, "context_text", _get(m, "context", "")),
                float(_get(m, "confidence", 0.0)),
            )
            for m in mentions
        ]
        self.conn.executemany(
            "INSERT INTO dimensions(file_id, raw_text, role, value, unit, context, confidence) VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        self.conn.commit()

    def add_situations(self, file_id: str, mentions: Iterable[Any]) -> None:
        rows = [
            (file_id, _get(m, "tag", ""), _get(m, "evidence_text", _get(m, "evidence", "")), float(_get(m, "confidence", 0.0)))
            for m in mentions
        ]
        self.conn.executemany("INSERT INTO situations(file_id, tag, evidence, confidence) VALUES (?, ?, ?, ?)", rows)
        self.conn.commit()

    def add_elements(self, file_id: str, mentions: Iterable[Any]) -> None:
        rows = [
            (
                file_id,
                _get(m, "canonical_element", ""),
                _get(m, "evidence", ""),
                _get(m, "source_kind", ""),
                float(_get(m, "confidence", 0.0)),
            )
            for m in mentions
        ]
        self.conn.executemany(
            "INSERT INTO canonical_elements(file_id, canonical_element, evidence, source_kind, confidence) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        self.conn.commit()

    def add_detail_patterns(self, file_id: str, patterns: Iterable[Any]) -> None:
        rows = [
            (
                file_id,
                _get(p, "pattern_name", ""),
                _get(p, "situation_tag", ""),
                json.dumps(_get(p, "elements", []), ensure_ascii=False),
                json.dumps(_get(p, "materials", []), ensure_ascii=False),
                json.dumps(_get(p, "typical_dimensions", _get(p, "dimensions", [])), ensure_ascii=False),
                json.dumps(_get(p, "notes", []), ensure_ascii=False),
                float(_get(p, "confidence", 0.0)),
            )
            for p in patterns
        ]
        self.conn.executemany(
            """
            INSERT INTO detail_patterns(file_id, pattern_name, situation_tag, elements_json, materials_json, dimensions_json, notes_json, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.conn.commit()

    def add_lesson(self, situation_tag: str, lesson: str, evidence_count: int, confidence: float) -> None:
        self.conn.execute(
            "INSERT INTO architectural_lessons(situation_tag, lesson, evidence_count, confidence) VALUES (?, ?, ?, ?)",
            (situation_tag, lesson, int(evidence_count), float(confidence)),
        )
        try:
            self.conn.execute("INSERT INTO lessons_fts(situation_tag, lesson) VALUES (?, ?)", (situation_tag, lesson))
        except sqlite3.OperationalError:
            pass
        self.conn.commit()

    def table_counts(self) -> dict[str, int]:
        tables = [
            "files", "fileized_records", "texts", "materials", "specifications", "dimensions",
            "situations", "canonical_elements", "detail_patterns", "architectural_lessons", "processing_errors",
        ]
        result = {}
        for table in tables:
            result[table] = int(self.conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"])
        return result

    def top_values(self, table: str, column: str, limit: int = 20) -> list[dict[str, Any]]:
        sql = f"SELECT {column} AS value, COUNT(*) AS count FROM {table} WHERE {column} IS NOT NULL AND {column} != '' GROUP BY {column} ORDER BY count DESC LIMIT ?"
        return [dict(r) for r in self.conn.execute(sql, (limit,)).fetchall()]

    def search(self, query: str, limit: int = 20) -> dict[str, list[dict[str, Any]]]:
        q = f"%{query}%"
        result: dict[str, list[dict[str, Any]]] = {}
        result["texts"] = [dict(r) for r in self.conn.execute("SELECT * FROM texts WHERE text LIKE ? OR context LIKE ? LIMIT ?", (q, q, limit)).fetchall()]
        result["materials"] = [dict(r) for r in self.conn.execute("SELECT * FROM materials WHERE name LIKE ? OR normalized_name LIKE ? OR context LIKE ? LIMIT ?", (q, q, q, limit)).fetchall()]
        result["specifications"] = [dict(r) for r in self.conn.execute("SELECT * FROM specifications WHERE raw_text LIKE ? OR normalized_value LIKE ? OR context LIKE ? LIMIT ?", (q, q, q, limit)).fetchall()]
        result["situations"] = [dict(r) for r in self.conn.execute("SELECT * FROM situations WHERE tag LIKE ? OR evidence LIKE ? LIMIT ?", (q, q, limit)).fetchall()]
        result["patterns"] = [dict(r) for r in self.conn.execute("SELECT * FROM detail_patterns WHERE pattern_name LIKE ? OR situation_tag LIKE ? OR notes_json LIKE ? LIMIT ?", (q, q, q, limit)).fetchall()]
        result["lessons"] = [dict(r) for r in self.conn.execute("SELECT * FROM architectural_lessons WHERE situation_tag LIKE ? OR lesson LIKE ? LIMIT ?", (q, q, limit)).fetchall()]
        return result


def _get(obj: Any, attr: str, default=None):
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)
