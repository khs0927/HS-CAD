from __future__ import annotations

from collections import Counter
from typing import Any


def summarize_objects(objects: list[dict[str, Any]]) -> dict[str, Any]:
    layer_counts = Counter(str(item.get("layer") or "0") for item in objects)
    type_counts = Counter(str(item.get("entity_type") or item.get("object_name") or item.get("dxftype") or "UNKNOWN") for item in objects)
    return {
        "object_count": len(objects),
        "layer_counts": dict(sorted(layer_counts.items())),
        "type_counts": dict(sorted(type_counts.items())),
    }


def build_delta_report(before_objects: list[dict[str, Any]], after_objects: list[dict[str, Any]]) -> dict[str, Any]:
    before = summarize_objects(before_objects)
    after = summarize_objects(after_objects)
    return {
        "before": before,
        "after": after,
        "delta": {
            "object_count": after["object_count"] - before["object_count"],
            "layer_counts": _counter_delta(before["layer_counts"], after["layer_counts"]),
            "type_counts": _counter_delta(before["type_counts"], after["type_counts"]),
        },
    }


def _counter_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    keys = sorted(set(before) | set(after))
    return {key: int(after.get(key, 0)) - int(before.get(key, 0)) for key in keys}
