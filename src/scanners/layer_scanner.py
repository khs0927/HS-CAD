from __future__ import annotations
from collections import Counter

def layer_counts(objects: list[dict]) -> dict[str, int]:
    c = Counter(str(o.get('layer') or '<NO_LAYER>') for o in objects)
    return dict(sorted(c.items()))
