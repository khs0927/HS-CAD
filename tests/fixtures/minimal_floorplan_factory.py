"""Generate tiny DXF fixtures at test runtime."""
from __future__ import annotations

from pathlib import Path


def write_minimal_floorplan_dxf(path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "0", "SECTION", "2", "ENTITIES",
        "0", "LINE", "8", "WAL1", "10", "0", "20", "0", "11", "1000", "21", "0",
        "0", "LINE", "8", "WAL1", "10", "1000", "20", "0", "11", "1000", "21", "800",
        "0", "LINE", "8", "WAL1", "10", "1000", "20", "800", "11", "0", "21", "800",
        "0", "LINE", "8", "WAL1", "10", "0", "20", "800", "11", "0", "21", "0",
        "0", "TEXT", "8", "TEXT", "10", "120", "20", "400", "40", "120", "1", "ROOM 101",
        "0", "TEXT", "8", "DIMLE", "10", "120", "20", "250", "40", "100", "1", "AREA 8.0 m2",
        "0", "ENDSEC", "0", "EOF",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
