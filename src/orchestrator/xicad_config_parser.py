'''Parse XiCAD configuration files used for layer/style mapping.

The files are plain text and may contain Korean characters, so we use the same
fallback-encoding strategy as the taxonomy parser.
'''  

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any

def _read_lines_safe(file_path: Path) -> List[str]:
    if not file_path.exists():
        return []
    encodings = ["cp949", "utf-8", "euc-kr", "latin1"]
    for enc in encodings:
        try:
            return [ln.rstrip('\n') for ln in file_path.read_text(encoding=enc).splitlines()]
        except Exception:
            continue
    return []

# ---------------------------------------------------------------------------
# xiDrawWall.txt - wall style definitions
# ---------------------------------------------------------------------------

def parse_xidraw_wall(file_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Parse ``xiDrawWall.txt``.

    The file groups wall styles with a ``*****GroupName: description`` header and
    then lines of ``offset;layer;color;linetype``.  The function returns a mapping
    ``group_name -> list of line dicts``.
    """
    lines = _read_lines_safe(file_path)
    result: Dict[str, List[Dict[str, Any]]] = {}
    current_group: str | None = None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("*****"):
            # New group header.
            parts = line.split(":", 1)
            grp = parts[0].replace("*****", "").strip()
            desc = parts[1].strip() if len(parts) > 1 else ""
            current_group = f"{grp} ({desc})" if desc else grp
            result[current_group] = []
            continue
        if current_group is None:
            continue
        # Expected: offset;layer;color;linetype
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 2:
            continue
        try:
            offset = float(parts[0])
        except ValueError:
            continue
        layer = parts[1]
        color = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 7
        ltype = parts[3] if len(parts) > 3 else "Continuous"
        result[current_group].append({
            "offset": offset,
            "layer": layer,
            "color": color,
            "linetype": ltype,
        })
    return result

# ---------------------------------------------------------------------------
# xiBlkLayerSet.txt - block-to-layer mapping
# ---------------------------------------------------------------------------

def parse_xiblock_layer_set(file_path: Path) -> Dict[str, Dict[str, Any]]:
    """Parse ``xiBlkLayerSet.txt``.

    Each line has the format ``symbol ; layer ; linetype ; color ; description``.
    The function returns a dict keyed by ``symbol``.
    """
    lines = _read_lines_safe(file_path)
    mapping: Dict[str, Dict[str, Any]] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith(";") or line.startswith("분류"):
            continue
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 4:
            continue
        symbol = parts[0]
        layer = parts[1]
        linetype = parts[2]
        color = int(parts[3]) if parts[3].isdigit() else 7
        description = parts[4] if len(parts) > 4 else ""
        mapping[symbol] = {
            "layer": layer,
            "linetype": linetype,
            "color": color,
            "description": description,
        }
    return mapping

# ---------------------------------------------------------------------------
# Layer_Setting.lay - basic layer defaults (color, linetype, etc.)
# ---------------------------------------------------------------------------

def parse_layer_setting(file_path: Path) -> Dict[str, Dict[str, Any]]:
    """Parse ``Layer_Setting.lay``.

    The format is a series of lines ``layer_name, color, linetype, lineweight``.
    Empty or comment lines are ignored.
    """
    lines = _read_lines_safe(file_path)
    settings: Dict[str, Dict[str, Any]] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        layer = parts[0]
        color = int(parts[1]) if parts[1].isdigit() else 7
        linetype = parts[2] if len(parts) > 2 else "Continuous"
        lineweight = parts[3] if len(parts) > 3 else "0.25"
        settings[layer] = {
            "color": color,
            "linetype": linetype,
            "lineweight": lineweight,
        }
    return settings
