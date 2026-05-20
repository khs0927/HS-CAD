from __future__ import annotations

def extract_dimensions(objects: list[dict]) -> list[dict]:
    return [o for o in objects if 'dim' in str(o.get('object_name') or '').lower()]
