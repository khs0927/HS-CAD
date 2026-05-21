"""Simple JSON manifest handling for the corpus workflow.

The manifest is a list of file‑metadata dictionaries (see ``CorpusFile`` in
``models.py``).  The class provides ``load`` and ``dump`` helpers and a small
utility to merge new entries while preserving existing state.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any

from .models import CorpusFile


class Manifest:
    """Container for a list of ``CorpusFile`` records.

    The manifest is stored as a JSON array.  Duplicate ``file_id`` entries are
    merged – the newer entry (based on ``modified_time``) wins.
    """

    def __init__(self, records: List[Dict[str, Any]] | None = None):
        self.records: List[Dict[str, Any]] = records or []
        self._index: Dict[str, Dict[str, Any]] = {r["file_id"]: r for r in self.records}

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        if not path.is_file():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return cls(data)
        raise ValueError("Invalid manifest format – expected a JSON array")

    def dump(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)

    def add_or_update(self, entry: Dict[str, Any]) -> None:
        fid = entry.get("file_id")
        if not fid:
            return
        existing = self._index.get(fid)
        if existing:
            # Prefer newer modification time
            if entry.get("modified_time", 0) > existing.get("modified_time", 0):
                self._index[fid] = entry
        else:
            self._index[fid] = entry
        self.records = list(self._index.values())
