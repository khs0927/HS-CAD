from __future__ import annotations
from src.cad_core.base import CADAdapter

def scan_objects(adapter: CADAdapter) -> list[dict]:
    return adapter.scan_modelspace()
