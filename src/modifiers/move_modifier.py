from __future__ import annotations
from src.cad_core.base import CADAdapter

def move_layer(adapter: CADAdapter, layer: str, dx: float, dy: float, dz: float = 0) -> int:
    if not layer:
        raise ValueError('layer is required')
    return adapter.move_layer(layer, dx, dy, dz)

def move_object_by_handle(adapter: CADAdapter, handle: str, dx: float, dy: float, dz: float = 0) -> int:
    if not handle:
        raise ValueError('handle is required')
    return adapter.move_entity(handle, dx, dy, dz)
