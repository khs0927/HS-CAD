from __future__ import annotations
from src.utils.geometry import bbox_from_points

def closed_polyline_candidates(objects: list[dict]) -> list[dict]:
    out: list[dict] = []
    for o in objects:
        if o.get('closed') is True and o.get('points'):
            item = dict(o)
            item['bbox'] = bbox_from_points(item['points'])
            out.append(item)
    return out
