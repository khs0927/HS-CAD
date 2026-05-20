from __future__ import annotations

def planned_offset_polyline(handle: str, dx: float, dy: float) -> dict:
    return {'action': 'offset_polyline', 'handle': handle, 'dx': dx, 'dy': dy, 'status': 'planned'}
