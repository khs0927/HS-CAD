"""SQLite search ranker for HS-CAD corpus.

The ranker is intentionally simple and dependency-free. It works with the
existing corpus SQLite schema even when optional FTS5 tables are not available.
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .query_expander import expand_query, tokenize


TEXTLIKE_TABLES = [
    "texts",
    "materials",
    "specifications",
    "dimensions",
    "situations",
    "detail_patterns",
    "architectural_lessons",
    "canonical_elements",
]


@dataclass
class SearchHit:
    table: str
    rowid: int | None
    file_id: str | None
    title: str
    text: str
    score: float
    payload: dict[str, Any] = field(default_factory=dict)


def _connect(kb_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(kb_path))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    if not _table_exists(conn, table):
        return []
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _row_text(row: sqlite3.Row, columns: list[str]) -> str:
    parts: list[str] = []
    preferred = [
        "text",
        "raw_text",
        "normalized_text",
        "material_name",
        "normalized_name",
        "spec_type",
        "raw_value",
        "normalized_value",
        "situation_tag",
        "tag",
        "pattern_name",
        "lesson",
        "notes",
        "context_text",
        "evidence_text",
        "entity_type",
        "canonical_element",
    ]
    for col in preferred:
        if col in columns:
            value = row[col]
            if value is not None:
                parts.append(str(value))
    if not parts:
        for col in columns:
            value = row[col]
            if isinstance(value, (str, int, float)) and value is not None:
                parts.append(str(value))
    return " ".join(parts)


def _file_id(row: sqlite3.Row, columns: list[str]) -> str | None:
    for key in ("file_id", "source_file_id", "record_id"):
        if key in columns and row[key]:
            return str(row[key])
    return None


def _score_text(text: str, query_terms: list[str]) -> float:
    if not text:
        return 0.0
    low = text.lower()
    tokens = tokenize(low)
    token_counts: dict[str, int] = {}
    for token in tokens:
        token_counts[token] = token_counts.get(token, 0) + 1

    score = 0.0
    for term in query_terms:
        term_l = term.lower()
        if not term_l:
            continue
        exact = low.count(term_l)
        if exact:
            score += 3.0 * exact
        if term_l in token_counts:
            score += 2.0 * token_counts[term_l]
        # soft substring for Korean compound terms
        for token, count in token_counts.items():
            if len(term_l) >= 2 and (term_l in token or token in term_l):
                score += 0.5 * count
    # avoid extremely long row dominance
    return score / math.sqrt(max(len(tokens), 1))


class CorpusSearchRanker:
    def __init__(self, kb_path: str | Path):
        self.kb_path = Path(kb_path)

    def search(self, query: str, limit: int = 25, tables: list[str] | None = None) -> list[SearchHit]:
        expanded = expand_query(query)
        terms = expanded.all_terms
        if not terms:
            return []

        conn = _connect(self.kb_path)
        try:
            hits: list[SearchHit] = []
            for table in tables or TEXTLIKE_TABLES:
                if not _table_exists(conn, table):
                    continue
                cols = _columns(conn, table)
                select_cols = ", ".join([f'"{c}"' for c in cols])
                for row in conn.execute(f"SELECT rowid, {select_cols} FROM {table} LIMIT 5000"):
                    text = _row_text(row, cols)
                    score = _score_text(text, terms)
                    if score <= 0:
                        continue
                    payload = {c: row[c] for c in cols if c in row.keys()}
                    title = str(payload.get("title") or payload.get("pattern_name") or payload.get("material_name") or payload.get("situation_tag") or table)
                    hits.append(
                        SearchHit(
                            table=table,
                            rowid=row["rowid"],
                            file_id=_file_id(row, cols),
                            title=title,
                            text=text[:1000],
                            score=score,
                            payload=payload,
                        )
                    )
            hits.sort(key=lambda h: h.score, reverse=True)
            return self._dedup(hits)[:limit]
        finally:
            conn.close()

    @staticmethod
    def _dedup(hits: list[SearchHit]) -> list[SearchHit]:
        seen: set[tuple[str, str, str]] = set()
        out: list[SearchHit] = []
        for hit in hits:
            key = (hit.table, hit.file_id or "", hit.text[:160])
            if key in seen:
                continue
            seen.add(key)
            out.append(hit)
        return out


def search_corpus(kb_path: str | Path, query: str, limit: int = 25) -> list[dict[str, Any]]:
    ranker = CorpusSearchRanker(kb_path)
    return [
        {
            "table": hit.table,
            "rowid": hit.rowid,
            "file_id": hit.file_id,
            "title": hit.title,
            "text": hit.text,
            "score": hit.score,
            "payload": hit.payload,
        }
        for hit in ranker.search(query=query, limit=limit)
    ]
