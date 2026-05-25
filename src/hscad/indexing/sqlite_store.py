"""SQLite evidence/entity store for local indexing."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from hscad.core.evidence import Evidence
from hscad.core.models import DrawingEntity, FileizedDrawing


SCHEMA = """
CREATE TABLE IF NOT EXISTS drawings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  input_path TEXT NOT NULL,
  source_format TEXT NOT NULL,
  metadata_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  drawing_id INTEGER NOT NULL,
  entity_id TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  layer TEXT NOT NULL,
  text TEXT,
  geometry_json TEXT NOT NULL,
  raw_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  drawing_id INTEGER NOT NULL,
  evidence_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  message TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
"""


class SqliteEvidenceStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def init(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA)

    def add_drawing(self, drawing: FileizedDrawing, evidence: list[Evidence] | None = None) -> int:
        self.init()
        with sqlite3.connect(self.path) as conn:
            cur = conn.execute("INSERT INTO drawings(input_path, source_format, metadata_json) VALUES (?, ?, ?)", (drawing.input_path, drawing.source_format, json.dumps(drawing.metadata, ensure_ascii=False)))
            drawing_id = int(cur.lastrowid)
            for ent in drawing.entities:
                conn.execute(
                    "INSERT INTO entities(drawing_id, entity_id, entity_type, layer, text, geometry_json, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (drawing_id, ent.entity_id, ent.entity_type, ent.layer, ent.text, json.dumps(ent.geometry, ensure_ascii=False), json.dumps(ent.raw, ensure_ascii=False)),
                )
            for ev in [*(drawing.evidence or []), *(evidence or [])]:
                record = ev.to_record() if hasattr(ev, "to_record") else ev
                conn.execute("INSERT INTO evidence(drawing_id, evidence_id, kind, message, payload_json) VALUES (?, ?, ?, ?, ?)", (drawing_id, record.get("evidence_id", "unknown"), record.get("kind", "unknown"), record.get("message", ""), json.dumps(record, ensure_ascii=False)))
            return drawing_id

    def counts(self) -> dict[str, int]:
        self.init()
        with sqlite3.connect(self.path) as conn:
            return {
                "drawings": conn.execute("SELECT COUNT(*) FROM drawings").fetchone()[0],
                "entities": conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0],
                "evidence": conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0],
            }
