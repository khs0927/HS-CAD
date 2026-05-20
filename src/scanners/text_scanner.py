from __future__ import annotations

def extract_texts(objects: list[dict]) -> list[dict]:
    out: list[dict] = []
    for o in objects:
        object_name = str(o.get('object_name') or '').lower()
        if 'text' in object_name:
            out.append({'handle': o.get('handle'), 'layer': o.get('layer'), 'insert': o.get('insert'), 'text': o.get('text'), 'rotation': o.get('rotation')})
    return out
