"""Export corpus records to JSONL for local RAG/search review datasets."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def _connect(kb_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(kb_path))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _fetch_by_file(conn: sqlite3.Connection, table: str) -> dict[str, list[dict[str, Any]]]:
    if not _table_exists(conn, table):
        return {}
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]
    if "file_id" not in cols:
        return {}
    rows: dict[str, list[dict[str, Any]]] = {}
    for row in conn.execute(f"SELECT * FROM {table} LIMIT 50000"):
        file_id = str(row["file_id"])
        rows.setdefault(file_id, []).append({c: row[c] for c in cols})
    return rows


def export_corpus_jsonl(kb_path: str | Path, out_path: str | Path, include_paths: bool = False) -> int:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    conn = _connect(kb_path)
    try:
        files: list[dict[str, Any]] = []
        if _table_exists(conn, "files"):
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(files)")]
            for row in conn.execute("SELECT * FROM files LIMIT 50000"):
                payload = {c: row[c] for c in cols}
                if not include_paths:
                    for key in ("source_path", "full_path", "path"):
                        if key in payload:
                            payload[key] = None
                files.append(payload)
        else:
            # If no files table exists, derive file ids from texts.
            file_ids = set()
            for table in ("texts", "materials", "specifications", "situations"):
                if _table_exists(conn, table):
                    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]
                    if "file_id" in cols:
                        file_ids.update(str(r["file_id"]) for r in conn.execute(f"SELECT DISTINCT file_id FROM {table}"))
            files = [{"file_id": fid} for fid in sorted(file_ids)]

        grouped = {
            "texts": _fetch_by_file(conn, "texts"),
            "materials": _fetch_by_file(conn, "materials"),
            "specifications": _fetch_by_file(conn, "specifications"),
            "dimensions": _fetch_by_file(conn, "dimensions"),
            "situations": _fetch_by_file(conn, "situations"),
            "canonical_elements": _fetch_by_file(conn, "canonical_elements"),
            "detail_patterns": _fetch_by_file(conn, "detail_patterns"),
        }

        count = 0
        with out.open("w", encoding="utf-8") as f:
            for file_row in files:
                file_id = str(file_row.get("file_id") or file_row.get("id") or file_row.get("hash") or count)
                record = {"file_id": file_id, "file": file_row}
                for name, mapping in grouped.items():
                    record[name] = mapping.get(file_id, [])
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
        return count
    finally:
        conn.close()
