"""Index discovered files into a SQLite knowledge store.

The implementation is intentionally lightweight – it records the file
metadata from the manifest and creates placeholder JSON records.  Full
extraction of drawing contents is outside the scope of this minimal version
but the infrastructure is ready for future extensions.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from .manifest import Manifest


def _ensure_tables(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            file_id TEXT PRIMARY KEY,
            path TEXT,
            filename TEXT,
            extension TEXT,
            size_bytes INTEGER,
            modified_time REAL,
            relative_path TEXT,
            status TEXT,
            error_message TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            record_id TEXT PRIMARY KEY,
            source_file_id TEXT,
            json_content TEXT,
            FOREIGN KEY(source_file_id) REFERENCES files(file_id)
        )
        """
    )
    conn.commit()


def index_manifest(
    manifest_path: Path,
    out_dir: Path,
    limit: Optional[int] = None,
) -> None:
    """Read *manifest_path*, write JSON records and populate SQLite.

    ``out_dir`` must contain a ``records`` sub‑directory for the per‑file JSON
    files and the SQLite database ``cad_knowledge.sqlite``.
    """

    manifest = Manifest.load(manifest_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    records_dir = out_dir / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    db_path = out_dir / "cad_knowledge.sqlite"
    conn = sqlite3.connect(db_path)
    _ensure_tables(conn)
    cur = conn.cursor()
    processed = 0
    for entry in manifest.records:
        if limit is not None and processed >= limit:
            break
        fid = entry.get("file_id")
        # Insert into files table – ignore duplicates
        cur.execute(
            "INSERT OR REPLACE INTO files (file_id, path, filename, extension, size_bytes, modified_time, relative_path, status, error_message) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                fid,
                entry.get("path"),
                entry.get("filename"),
                entry.get("extension"),
                entry.get("size_bytes"),
                entry.get("modified_time"),
                entry.get("relative_path"),
                entry.get("status"),
                entry.get("error_message"),
            ),
        )
        # Write placeholder JSON record
        record = {
            "record_id": f"rec_{fid}",
            "source_file_id": fid,
            "json_content": {},
        }
        record_path = records_dir / f"{fid}.json"
        with record_path.open("w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        # Insert into records table
        cur.execute(
            "INSERT OR REPLACE INTO records (record_id, source_file_id, json_content) VALUES (?,?,?)",
            (record["record_id"], fid, json.dumps(record["json_content"]))
        )
        processed += 1
    conn.commit()
    conn.close()
