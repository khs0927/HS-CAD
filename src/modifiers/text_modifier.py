from __future__ import annotations
from src.cad_core.base import CADAdapter

def replace_text(adapter: CADAdapter, find: str, replace: str, layer: str | None = None) -> int:
    if not find:
        raise ValueError('find text is required')
    return adapter.replace_text(find, replace, layer)
