from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.corpus.text_extraction import normalize_search_text


class CorpusQuery:
    def __init__(self, sqlite_path: str | Path):
        self.sqlite_path = Path(sqlite_path)

    def search_text(self, query: str, *, limit: int = 20) -> dict:
        text = query.strip()
        if not text:
            return {"query": query, "matches": [], "warnings": [{"type": "empty_query"}]}
        if not self.sqlite_path.exists():
            return {
                "query": query,
                "matches": [],
                "warnings": [{"type": "missing_index", "path": str(self.sqlite_path)}],
            }
        with sqlite3.connect(str(self.sqlite_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = self._search_v2(conn, text, limit)
            if not rows:
                rows = self._search_fts(conn, text, limit)
            if not rows:
                rows = self._search_like(conn, text, limit)
        return {
            "query": query,
            "normalized_query": normalize_search_text(query),
            "matches": rows,
            "warnings": [] if rows else [{"type": "no_matches"}],
        }

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name=? LIMIT 1", (name,)
        ).fetchone() is not None

    def _search_v2(
        self, conn: sqlite3.Connection, query: str, limit: int
    ) -> list[dict]:
        if not self._table_exists(conn, "text_fts_v2"):
            return []
        candidates = [query]
        normalized = normalize_search_text(query)
        if normalized and normalized != query:
            candidates.append(normalized)
        rows: list[sqlite3.Row] = []
        for candidate in candidates:
            try:
                rows = conn.execute(
                    """
                    SELECT
                      f.file_id, f.source_path, f.relative_path, f.extension, f.engine,
                      o.occurrence_id, o.handle, o.sub_handle, o.layer, o.entity_type,
                      o.layout, o.space, o.block_path_json, o.source_kind, o.tag,
                      o.row_number, o.column_number, o.raw_text,
                      o.plain_text AS text, o.normalized_text,
                      o.x, o.y, o.z, o.bbox_json, o.confidence, o.xref_path,
                      o.payload_json, bm25(text_fts_v2) AS score
                    FROM text_fts_v2
                    JOIN text_occurrences o
                      ON o.file_id = text_fts_v2.file_id
                     AND o.occurrence_id = text_fts_v2.occurrence_id
                    JOIN files f ON f.file_id = o.file_id
                    WHERE text_fts_v2 MATCH ?
                    ORDER BY score
                    LIMIT ?
                    """,
                    (candidate, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
            if rows:
                break
        out: list[dict] = []
        for row in rows:
            item = dict(row)
            for key in ("block_path_json", "bbox_json", "payload_json"):
                raw = item.pop(key, None)
                target = key.removesuffix("_json")
                if raw:
                    try:
                        item[target] = json.loads(raw)
                    except Exception:
                        item[target] = raw
                else:
                    item[target] = [] if target == "block_path" else None
            out.append(item)
        return out

    def _search_fts(
        self, conn: sqlite3.Connection, query: str, limit: int
    ) -> list[dict]:
        try:
            rows = conn.execute(
                """
                SELECT f.file_id, f.relative_path, t.layer, t.text, rank
                FROM text_fts t
                JOIN files f ON f.file_id = t.file_id
                WHERE text_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
            return [dict(row) for row in rows]
        except Exception:
            return []

    def _search_like(
        self, conn: sqlite3.Connection, query: str, limit: int
    ) -> list[dict]:
        rows = conn.execute(
            """
            SELECT f.file_id, f.relative_path, t.layer, t.text, t.payload_json
            FROM texts t
            JOIN files f ON f.file_id = t.file_id
            WHERE t.text LIKE ?
            LIMIT ?
            """,
            (f"%{query}%", limit),
        ).fetchall()
        out: list[dict] = []
        for row in rows:
            item = dict(row)
            payload = item.pop("payload_json", None)
            if payload:
                try:
                    item["payload"] = json.loads(payload)
                except Exception:
                    item["payload"] = payload
            out.append(item)
        return out
