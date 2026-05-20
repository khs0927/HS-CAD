from __future__ import annotations
from src.cad_core.base import CADAdapter

def list_layers(adapter: CADAdapter) -> list[str]:
    return adapter.list_layers()
