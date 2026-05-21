"""Optional active drawing context loader.

This module does not talk to ZWCAD directly. It loads JSON outputs produced by
existing HS-CAD local style sampling tools when they are available.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


COMMON_CONTEXT_PATHS = [
    "outputs/style_sample_current",
    "outputs/zium_sheet_area_current",
    "generated",
]


def find_active_context_files(repo_root: str | Path = ".") -> list[Path]:
    root = Path(repo_root)
    paths: list[Path] = []
    for rel in COMMON_CONTEXT_PATHS:
        base = root / rel
        if base.exists():
            paths.extend(base.rglob("*.json"))
    return sorted(paths)


def load_active_context(repo_root: str | Path = ".") -> dict[str, Any]:
    context: dict[str, Any] = {"source_files": [], "samples": []}
    for path in find_active_context_files(repo_root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            context.setdefault("warnings", []).append(f"Failed to load {path}: {exc}")
            continue
        context["source_files"].append(str(path))
        context["samples"].append(data)
    return context
