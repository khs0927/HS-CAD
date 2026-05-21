"""Simple heuristic classifier for drawing files.

The classifier returns a dictionary with ``category`` (floor_plan, section,
etc.) and optional ``project_name`` guess based on the file path.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional

# Mapping of keywords to canonical drawing categories
_CATEGORY_KEYWORDS = {
    "plan": ["plan", "floor", "플랜", "평면", "floorplan"],
    "section": ["section", "sec", "단면", "section"],
    "elevation": ["elev", "elevation", "입면", "elev"],
    "detail": ["detail", "det", "상세", "detail"],
    "schedule": ["schedule", "schedules", "표", "schedule"],
    "structural": ["struct", "structure", "구조", "structural"],
    "mechanical": ["mechanical", "설비", "mech"],
    "electrical": ["electrical", "전기", "elec"],
    "fire": ["fire", "소방", "fire"],
    "civil": ["civil", "토목", "civil"],
}


def classify_file(file_path: Path) -> Dict[str, Optional[str]]:
    """Return a simple classification for *file_path*.

    The result contains:
        - ``category``: one of the keys in ``_CATEGORY_KEYWORDS`` or ``unknown``
        - ``project_name``: heuristic project name extracted from parent
          directories (first non‑numeric component)
    """

    name = file_path.stem.lower()
    category = "unknown"
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name:
                category = cat
                break
        if category != "unknown":
            break
    # Heuristic project name: first directory component that contains a letter
    parts = list(file_path.parts)
    project_name: Optional[str] = None
    for part in parts:
        if re.search(r"[A-Za-z가-힣]", part):
            project_name = part
            break
    return {"category": category, "project_name": project_name}
