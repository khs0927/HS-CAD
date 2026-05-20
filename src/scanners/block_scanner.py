from __future__ import annotations
from collections import defaultdict

def block_summary(objects: list[dict]) -> dict[str, dict]:
    summary: dict[str, dict] = defaultdict(lambda: {'count': 0, 'inserts': []})
    for o in objects:
        name = o.get('name')
        if name:
            summary[str(name)]['count'] += 1
            summary[str(name)]['inserts'].append({'handle': o.get('handle'), 'insert': o.get('insert'), 'rotation': o.get('rotation')})
    return dict(sorted(summary.items()))
