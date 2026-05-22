from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from src.corpus.schema import FileizedDrawingRecord


SCHEMA_SQL = '''
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
'''


class CorpusIndexer:
    def __init__(self, sqlite_path: str | Path):
        self.sqlite_path = Path(sqlite_path)

    def connect(self) -> sqlite3.Connection:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.sqlite_path))
        conn.executescript(SCHEMA_SQL)
        return conn

    def index_record(self, record: FileizedDrawingRecord) -> None:
        with self.connect() as conn:
            self._delete_existing(conn, record.file_id)
            conn.execute(
                'INSERT INTO files(file_id, source_path, relative_path, extension, status, engine, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (
                    record.file_id,
                    record.source_path,
                    record.relative_path,
                    record.extension,
                    record.status,
                    record.engine,
                    json.dumps(record.metadata, ensure_ascii=False),
                ),
            )
            for row in record.layers:
                conn.execute('INSERT INTO layers(file_id, name, entity_count) VALUES (?, ?, ?)', (record.file_id, str(row.get('name')), int(row.get('entity_count') or 0)))
            for row in record.entities:
                conn.execute(
                    'INSERT INTO entities(file_id, handle, entity_type, layer, payload_json) VALUES (?, ?, ?, ?, ?)',
                    (record.file_id, _s(row.get('handle')), _s(row.get('entity_type')), _s(row.get('layer')), json.dumps(row, ensure_ascii=False)),
                )
            for row in record.texts:
                text = str(row.get('text') or '').strip()
                if not text:
                    continue
                conn.execute(
                    'INSERT INTO texts(file_id, handle, layer, entity_type, text, payload_json) VALUES (?, ?, ?, ?, ?, ?)',
                    (record.file_id, _s(row.get('handle')), _s(row.get('layer')), _s(row.get('entity_type')), text, json.dumps(row, ensure_ascii=False)),
                )
                conn.execute('INSERT INTO text_fts(file_id, layer, text) VALUES (?, ?, ?)', (record.file_id, _s(row.get('layer')), text))
            for row in record.blocks:
                conn.execute('INSERT INTO blocks(file_id, name, count) VALUES (?, ?, ?)', (record.file_id, str(row.get('name')), int(row.get('count') or 0)))
            for row in record.dimensions:
                conn.execute(
                    'INSERT INTO dimensions(file_id, handle, layer, measurement, text_override, payload_json) VALUES (?, ?, ?, ?, ?, ?)',
                    (record.file_id, _s(row.get('handle')), _s(row.get('layer')), _s(row.get('measurement')), _s(row.get('text_override')), json.dumps(row, ensure_ascii=False)),
                )
            for item in record.warnings:
                conn.execute('INSERT INTO failures(file_id, kind, payload_json) VALUES (?, ?, ?)', (record.file_id, 'warning', json.dumps(item, ensure_ascii=False)))
            for item in record.errors:
                conn.execute('INSERT INTO failures(file_id, kind, payload_json) VALUES (?, ?, ?)', (record.file_id, 'error', json.dumps(item, ensure_ascii=False)))

    def index_json_dir(self, json_dir: str | Path) -> int:
        count = 0
        for path in sorted(Path(json_dir).glob('*.json')):
            payload = json.loads(path.read_text(encoding='utf-8'))
            self.index_record(FileizedDrawingRecord(**payload))
            count += 1
        return count

    def _delete_existing(self, conn: sqlite3.Connection, file_id: str) -> None:
        for table in ('files', 'layers', 'entities', 'texts', 'blocks', 'dimensions', 'failures'):
            conn.execute(f'DELETE FROM {table} WHERE file_id = ?', (file_id,))
        conn.execute('DELETE FROM text_fts WHERE file_id = ?', (file_id,))


def _s(value: object) -> str | None:
    return None if value is None else str(value)
