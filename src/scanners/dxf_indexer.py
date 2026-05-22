from __future__ import annotations

import shutil
import sqlite3
import subprocess
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
  handle TEXT PRIMARY KEY,
  type TEXT,
  layer TEXT,
  bbox_min_x REAL,
  bbox_min_y REAL,
  bbox_max_x REAL,
  bbox_max_y REAL,
  text TEXT,
  block_name TEXT,
  source TEXT
);
CREATE TABLE IF NOT EXISTS layers (
  name TEXT PRIMARY KEY,
  color INTEGER,
  linetype TEXT,
  lineweight INTEGER
);
CREATE TABLE IF NOT EXISTS blocks (
  name TEXT PRIMARY KEY,
  count INTEGER
);
CREATE TABLE IF NOT EXISTS texts (
  handle TEXT PRIMARY KEY,
  layer TEXT,
  text TEXT,
  x REAL,
  y REAL,
  height REAL,
  rotation REAL
);
"""


def convert_dwg_to_dxf(dwg: Path, out_dir: Path, oda_converter: str | None = None) -> Path:
    """Convert DWG to DXF through ODA File Converter when configured."""

    converter = oda_converter or shutil.which("ODAFileConverter") or shutil.which("ODAFileConverter.exe")
    if not converter:
        raise RuntimeError("ODA File Converter was not found. Provide --oda-converter or pass an existing DXF file.")
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [converter, str(dwg.parent), str(out_dir), "ACAD2018", "DXF", "0", "1", dwg.name],
        check=True,
        text=True,
        capture_output=True,
    )
    candidates = sorted(out_dir.glob(f"{dwg.stem}*.dxf"))
    if not candidates:
        raise RuntimeError(f"ODA conversion completed but no DXF was found in {out_dir}")
    return candidates[0]


def _bbox(entity: Any) -> tuple[float | None, float | None, float | None, float | None]:
    try:
        box = entity.bbox()
        return box.extmin.x, box.extmin.y, box.extmax.x, box.extmax.y
    except Exception:
        pass
    points = []
    try:
        if entity.dxftype() == "LINE":
            points = [entity.dxf.start, entity.dxf.end]
        elif entity.dxftype() in {"TEXT", "MTEXT", "INSERT"}:
            points = [entity.dxf.insert]
        elif hasattr(entity, "get_points"):
            points = [p for p in entity.get_points()]
    except Exception:
        points = []
    if not points:
        return None, None, None, None
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def index_dxf_to_sqlite(dxf: Path, sqlite_path: Path) -> dict[str, Any]:
    try:
        import ezdxf  # type: ignore
    except Exception as exc:
        raise RuntimeError("ezdxf is required for index-dxf. Install ezdxf or skip offline indexing.") from exc

    doc = ezdxf.readfile(dxf)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    if sqlite_path.exists():
        sqlite_path.unlink()
    conn = sqlite3.connect(sqlite_path)
    conn.executescript(SCHEMA)
    block_counts: dict[str, int] = {}
    entity_count = 0
    text_count = 0
    for entity in doc.modelspace():
        dxftype = entity.dxftype()
        handle = getattr(entity.dxf, "handle", None)
        layer = getattr(entity.dxf, "layer", None)
        xmin, ymin, xmax, ymax = _bbox(entity)
        text = None
        block_name = None
        if dxftype in {"TEXT", "MTEXT"}:
            text = entity.plain_text() if hasattr(entity, "plain_text") else getattr(entity.dxf, "text", None)
            text_count += 1
        if dxftype == "INSERT":
            block_name = getattr(entity.dxf, "name", None)
            if block_name:
                block_counts[block_name] = block_counts.get(block_name, 0) + 1
        conn.execute(
            "INSERT OR REPLACE INTO entities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (handle, dxftype, layer, xmin, ymin, xmax, ymax, text, block_name, str(dxf)),
        )
        if text is not None:
            insert = getattr(entity.dxf, "insert", (None, None, None))
            conn.execute(
                "INSERT OR REPLACE INTO texts VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    handle,
                    layer,
                    text,
                    float(insert[0]) if insert else None,
                    float(insert[1]) if insert else None,
                    getattr(entity.dxf, "height", None),
                    getattr(entity.dxf, "rotation", None),
                ),
            )
        entity_count += 1
    for layer in doc.layers:
        conn.execute(
            "INSERT OR REPLACE INTO layers VALUES (?, ?, ?, ?)",
            (layer.dxf.name, getattr(layer.dxf, "color", None), getattr(layer.dxf, "linetype", None), getattr(layer.dxf, "lineweight", None)),
        )
    for name, count in block_counts.items():
        conn.execute("INSERT OR REPLACE INTO blocks VALUES (?, ?)", (name, count))
    conn.commit()
    conn.close()
    return {"dxf": str(dxf), "sqlite": str(sqlite_path), "entities": entity_count, "texts": text_count, "blocks": len(block_counts)}


def query_index(sqlite_path: Path, where: str, limit: int = 200) -> list[dict[str, Any]]:
    if ";" in where:
        raise ValueError("Semicolons are not allowed in --where")
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(f"SELECT * FROM entities WHERE {where} LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]
