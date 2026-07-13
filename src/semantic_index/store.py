from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

import numpy as np

from src.semantic_index.schema import SearchHit, SemanticVector

SCHEMA_SQL = '''
CREATE TABLE IF NOT EXISTS semantic_drawings (
  file_id TEXT PRIMARY KEY,
  source_path TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  feature_version TEXT NOT NULL,
  vector_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_semantic_drawings_version
  ON semantic_drawings(feature_version);
'''


class SemanticIndexStore:
    """Small local vector store optimized for offline single-user use."""

    def __init__(self, sqlite_path: str | Path):
        self.sqlite_path = Path(sqlite_path)

    def connect(self) -> sqlite3.Connection:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.sqlite_path))
        connection.row_factory = sqlite3.Row
        connection.executescript(SCHEMA_SQL)
        return connection

    def upsert(self, item: SemanticVector) -> None:
        with self.connect() as connection:
            connection.execute(
                '''
                INSERT INTO semantic_drawings(
                  file_id, source_path, relative_path, feature_version, vector_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                  source_path=excluded.source_path,
                  relative_path=excluded.relative_path,
                  feature_version=excluded.feature_version,
                  vector_json=excluded.vector_json,
                  metadata_json=excluded.metadata_json,
                  indexed_at=CURRENT_TIMESTAMP
                ''',
                (
                    item.file_id,
                    item.source_path,
                    item.relative_path,
                    item.feature_version,
                    json.dumps(item.vector),
                    json.dumps(item.metadata, ensure_ascii=False),
                ),
            )

    def upsert_many(self, items: Iterable[SemanticVector]) -> int:
        count = 0
        with self.connect() as connection:
            for item in items:
                connection.execute(
                    '''
                    INSERT INTO semantic_drawings(
                      file_id, source_path, relative_path, feature_version, vector_json, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(file_id) DO UPDATE SET
                      source_path=excluded.source_path,
                      relative_path=excluded.relative_path,
                      feature_version=excluded.feature_version,
                      vector_json=excluded.vector_json,
                      metadata_json=excluded.metadata_json,
                      indexed_at=CURRENT_TIMESTAMP
                    ''',
                    (
                        item.file_id,
                        item.source_path,
                        item.relative_path,
                        item.feature_version,
                        json.dumps(item.vector),
                        json.dumps(item.metadata, ensure_ascii=False),
                    ),
                )
                count += 1
        return count

    def search(self, query: SemanticVector, *, limit: int = 10, exclude_file_id: str | None = None) -> list[SearchHit]:
        query_vector = np.asarray(query.vector, dtype=np.float32)
        if query_vector.ndim != 1:
            raise ValueError('query vector must be one-dimensional')
        with self.connect() as connection:
            rows = connection.execute(
                'SELECT * FROM semantic_drawings WHERE feature_version = ?',
                (query.feature_version,),
            ).fetchall()

        hits: list[SearchHit] = []
        for row in rows:
            if exclude_file_id and row['file_id'] == exclude_file_id:
                continue
            candidate = np.asarray(json.loads(row['vector_json']), dtype=np.float32)
            if candidate.shape != query_vector.shape:
                continue
            score = float(np.dot(query_vector, candidate))
            hits.append(
                SearchHit(
                    file_id=row['file_id'],
                    relative_path=row['relative_path'],
                    source_path=row['source_path'],
                    score=score,
                    feature_version=row['feature_version'],
                    metadata=json.loads(row['metadata_json'] or '{}'),
                )
            )
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[: max(1, limit)]

    def count(self, feature_version: str | None = None) -> int:
        with self.connect() as connection:
            if feature_version:
                row = connection.execute(
                    'SELECT COUNT(*) AS count FROM semantic_drawings WHERE feature_version = ?',
                    (feature_version,),
                ).fetchone()
            else:
                row = connection.execute('SELECT COUNT(*) AS count FROM semantic_drawings').fetchone()
        return int(row['count'] if row else 0)

    def clear(self, feature_version: str | None = None) -> int:
        with self.connect() as connection:
            if feature_version:
                cursor = connection.execute(
                    'DELETE FROM semantic_drawings WHERE feature_version = ?',
                    (feature_version,),
                )
            else:
                cursor = connection.execute('DELETE FROM semantic_drawings')
        return max(0, cursor.rowcount)
