from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class CorpusQuery:
    def __init__(self, sqlite_path: str | Path):
        self.sqlite_path = Path(sqlite_path)

    def search_text(self, query: str, *, limit: int = 20) -> dict:
        text = query.strip()
        if not text:
            return {'query': query, 'matches': [], 'warnings': [{'type': 'empty_query'}]}
        if not self.sqlite_path.exists():
            return {'query': query, 'matches': [], 'warnings': [{'type': 'missing_index', 'path': str(self.sqlite_path)}]}
        with sqlite3.connect(str(self.sqlite_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = self._search_fts(conn, text, limit)
            if not rows:
                rows = self._search_like(conn, text, limit)
        return {'query': query, 'matches': rows, 'warnings': [] if rows else [{'type': 'no_matches'}]}

    def _search_fts(self, conn: sqlite3.Connection, query: str, limit: int) -> list[dict]:
        try:
            rows = conn.execute(
                '''
                SELECT f.file_id, f.relative_path, t.layer, t.text, rank
                FROM text_fts t
                JOIN files f ON f.file_id = t.file_id
                WHERE text_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                ''',
                (query, limit),
            ).fetchall()
            return [dict(row) for row in rows]
        except Exception:
            return []

    def _search_like(self, conn: sqlite3.Connection, query: str, limit: int) -> list[dict]:
        rows = conn.execute(
            '''
            SELECT f.file_id, f.relative_path, t.layer, t.text, t.payload_json
            FROM texts t
            JOIN files f ON f.file_id = t.file_id
            WHERE t.text LIKE ?
            LIMIT ?
            ''',
            (f'%{query}%', limit),
        ).fetchall()
        out: list[dict] = []
        for row in rows:
            item = dict(row)
            payload = item.pop('payload_json', None)
            if payload:
                try:
                    item['payload'] = json.loads(payload)
                except Exception:
                    item['payload'] = payload
            out.append(item)
        return out
