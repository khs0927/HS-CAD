from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.corpus.schema import FileizedDrawingRecord
from src.corpus.text_extraction import normalize_search_text

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS files (
  file_id TEXT PRIMARY KEY,
  source_path TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  extension TEXT NOT NULL,
  status TEXT NOT NULL,
  engine TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS layers (
  file_id TEXT NOT NULL,
  name TEXT NOT NULL,
  entity_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS entities (
  file_id TEXT NOT NULL,
  handle TEXT,
  entity_type TEXT,
  layer TEXT,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS texts (
  file_id TEXT NOT NULL,
  handle TEXT,
  layer TEXT,
  entity_type TEXT,
  text TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS blocks (
  file_id TEXT NOT NULL,
  name TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS dimensions (
  file_id TEXT NOT NULL,
  handle TEXT,
  layer TEXT,
  measurement TEXT,
  text_override TEXT,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS failures (
  file_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS text_fts USING fts5(file_id, layer, text);

CREATE TABLE IF NOT EXISTS extraction_runs (
  file_id TEXT PRIMARY KEY,
  schema_version INTEGER NOT NULL,
  report_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS layouts (
  file_id TEXT NOT NULL,
  name TEXT NOT NULL,
  space TEXT,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS xrefs (
  file_id TEXT NOT NULL,
  name TEXT,
  path TEXT,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS text_occurrences (
  occurrence_id TEXT NOT NULL,
  file_id TEXT NOT NULL,
  handle TEXT,
  sub_handle TEXT,
  layer TEXT,
  entity_type TEXT,
  layout TEXT,
  space TEXT,
  block_path_json TEXT NOT NULL DEFAULT '[]',
  source_kind TEXT,
  tag TEXT,
  row_number INTEGER,
  column_number INTEGER,
  raw_text TEXT NOT NULL,
  plain_text TEXT NOT NULL,
  normalized_text TEXT NOT NULL,
  x REAL,
  y REAL,
  z REAL,
  bbox_json TEXT,
  confidence REAL NOT NULL DEFAULT 1.0,
  xref_path TEXT,
  payload_json TEXT NOT NULL,
  PRIMARY KEY (file_id, occurrence_id)
);
CREATE VIRTUAL TABLE IF NOT EXISTS text_fts_v2 USING fts5(
  occurrence_id UNINDEXED,
  file_id UNINDEXED,
  relative_path,
  layer,
  layout,
  block_path,
  plain_text,
  normalized_text,
  tokenize='unicode61 remove_diacritics 2'
);
CREATE INDEX IF NOT EXISTS text_occurrences_file_idx ON text_occurrences(file_id);
CREATE INDEX IF NOT EXISTS text_occurrences_layout_idx ON text_occurrences(layout);
CREATE INDEX IF NOT EXISTS text_occurrences_layer_idx ON text_occurrences(layer);
"""


class CorpusIndexer:
    def __init__(self, sqlite_path: str | Path):
        self.sqlite_path = Path(sqlite_path)

    def connect(self) -> sqlite3.Connection:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.sqlite_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA_SQL)
        return conn

    def index_record(self, record: FileizedDrawingRecord) -> None:
        with self.connect() as conn:
            self._delete_existing(conn, record.file_id)
            metadata = {
                **record.metadata,
                "schema_version": record.schema_version,
                "extraction_report": record.extraction_report,
            }
            conn.execute(
                "INSERT INTO files(file_id, source_path, relative_path, extension, status, engine, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    record.file_id,
                    record.source_path,
                    record.relative_path,
                    record.extension,
                    record.status,
                    record.engine,
                    json.dumps(metadata, ensure_ascii=False),
                ),
            )
            conn.execute(
                "INSERT INTO extraction_runs(file_id, schema_version, report_json) VALUES (?, ?, ?)",
                (
                    record.file_id,
                    int(record.schema_version),
                    json.dumps(record.extraction_report, ensure_ascii=False),
                ),
            )
            for row in record.layouts:
                conn.execute(
                    "INSERT INTO layouts(file_id, name, space, payload_json) VALUES (?, ?, ?, ?)",
                    (
                        record.file_id,
                        str(row.get("name") or ""),
                        _s(row.get("space")),
                        json.dumps(row, ensure_ascii=False),
                    ),
                )
            for row in record.xrefs:
                conn.execute(
                    "INSERT INTO xrefs(file_id, name, path, payload_json) VALUES (?, ?, ?, ?)",
                    (
                        record.file_id,
                        _s(row.get("name")),
                        _s(row.get("path")),
                        json.dumps(row, ensure_ascii=False),
                    ),
                )
            for row in record.layers:
                conn.execute(
                    "INSERT INTO layers(file_id, name, entity_count) VALUES (?, ?, ?)",
                    (
                        record.file_id,
                        str(row.get("name")),
                        int(row.get("entity_count") or 0),
                    ),
                )
            for row in record.entities:
                conn.execute(
                    "INSERT INTO entities(file_id, handle, entity_type, layer, payload_json) VALUES (?, ?, ?, ?, ?)",
                    (
                        record.file_id,
                        _s(row.get("handle")),
                        _s(row.get("entity_type")),
                        _s(row.get("layer")),
                        json.dumps(row, ensure_ascii=False),
                    ),
                )
            for row in record.texts:
                self._index_text(conn, record, row)
            for row in record.blocks:
                conn.execute(
                    "INSERT INTO blocks(file_id, name, count) VALUES (?, ?, ?)",
                    (
                        record.file_id,
                        str(row.get("name")),
                        int(row.get("count") or 0),
                    ),
                )
            for row in record.dimensions:
                conn.execute(
                    "INSERT INTO dimensions(file_id, handle, layer, measurement, text_override, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        record.file_id,
                        _s(row.get("handle")),
                        _s(row.get("layer")),
                        _s(row.get("measurement")),
                        _s(row.get("text_override")),
                        json.dumps(row, ensure_ascii=False),
                    ),
                )
            for item in record.warnings:
                conn.execute(
                    "INSERT INTO failures(file_id, kind, payload_json) VALUES (?, ?, ?)",
                    (record.file_id, "warning", json.dumps(item, ensure_ascii=False)),
                )
            for item in record.errors:
                conn.execute(
                    "INSERT INTO failures(file_id, kind, payload_json) VALUES (?, ?, ?)",
                    (record.file_id, "error", json.dumps(item, ensure_ascii=False)),
                )

    def _index_text(
        self,
        conn: sqlite3.Connection,
        record: FileizedDrawingRecord,
        row: dict,
    ) -> None:
        plain = str(row.get("plain_text") or row.get("text") or "").strip()
        if not plain:
            return
        raw = str(row.get("raw_text") or plain)
        normalized = str(row.get("normalized_text") or normalize_search_text(plain))
        occurrence_id = str(row.get("occurrence_id") or "")
        if not occurrence_id:
            import hashlib

            occurrence_id = hashlib.sha256(
                json.dumps(
                    {
                        "file_id": record.file_id,
                        "handle": row.get("handle"),
                        "layout": row.get("layout"),
                        "block_path": row.get("block_path"),
                        "text": plain,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                ).encode("utf-8")
            ).hexdigest()

        payload = json.dumps(row, ensure_ascii=False)
        conn.execute(
            "INSERT INTO texts(file_id, handle, layer, entity_type, text, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
            (
                record.file_id,
                _s(row.get("handle")),
                _s(row.get("layer")),
                _s(row.get("entity_type")),
                plain,
                payload,
            ),
        )
        conn.execute(
            "INSERT INTO text_fts(file_id, layer, text) VALUES (?, ?, ?)",
            (record.file_id, _s(row.get("layer")), plain),
        )
        position = row.get("insert") or []
        xyz = [None, None, None]
        try:
            for index, value in enumerate(list(position)[:3]):
                xyz[index] = float(value)
        except Exception:
            pass
        block_path = row.get("block_path") or []
        if isinstance(block_path, str):
            block_path = [block_path]
        conn.execute(
            """
            INSERT INTO text_occurrences(
              occurrence_id, file_id, handle, sub_handle, layer, entity_type,
              layout, space, block_path_json, source_kind, tag, row_number,
              column_number, raw_text, plain_text, normalized_text, x, y, z,
              bbox_json, confidence, xref_path, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                occurrence_id,
                record.file_id,
                _s(row.get("handle")),
                _s(row.get("sub_handle")),
                _s(row.get("layer")),
                _s(row.get("entity_type")),
                _s(row.get("layout") or "Model"),
                _s(row.get("space") or "model"),
                json.dumps(block_path, ensure_ascii=False),
                _s(row.get("source_kind")),
                _s(row.get("tag")),
                row.get("row"),
                row.get("column"),
                raw,
                plain,
                normalized,
                xyz[0],
                xyz[1],
                xyz[2],
                json.dumps(row.get("bbox"), ensure_ascii=False),
                float(row.get("confidence", 1.0)),
                _s(row.get("xref_path")),
                payload,
            ),
        )
        conn.execute(
            "INSERT INTO text_fts_v2(occurrence_id, file_id, relative_path, layer, layout, block_path, plain_text, normalized_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                occurrence_id,
                record.file_id,
                record.relative_path,
                _s(row.get("layer")),
                _s(row.get("layout") or "Model"),
                " > ".join(str(item) for item in block_path),
                plain,
                normalized,
            ),
        )

    def index_json_dir(self, json_dir: str | Path) -> int:
        count = 0
        for path in sorted(Path(json_dir).glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.index_record(FileizedDrawingRecord(**payload))
            count += 1
        return count

    def _delete_existing(self, conn: sqlite3.Connection, file_id: str) -> None:
        for table in (
            "files",
            "layers",
            "entities",
            "texts",
            "blocks",
            "dimensions",
            "failures",
            "extraction_runs",
            "layouts",
            "xrefs",
            "text_occurrences",
        ):
            conn.execute(f"DELETE FROM {table} WHERE file_id = ?", (file_id,))
        conn.execute("DELETE FROM text_fts WHERE file_id = ?", (file_id,))
        conn.execute("DELETE FROM text_fts_v2 WHERE file_id = ?", (file_id,))


def _s(value: object) -> str | None:
    return None if value is None else str(value)
