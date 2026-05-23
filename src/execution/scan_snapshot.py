from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DrawingScanSnapshot:
    source_dwg: str
    object_count: int
    layer_counts: dict[str, int]
    type_counts: dict[str, int]
    objects: list[dict[str, Any]]
    warnings: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_scan_snapshot(adapter: Any, dwg_path: str) -> DrawingScanSnapshot:
    adapter.open_document(dwg_path)
    objects = adapter.scan_modelspace()
    warnings = list(getattr(adapter, "warnings", []) or [])
    return snapshot_from_objects(dwg_path, objects, warnings=warnings)


def snapshot_from_objects(
    source_dwg: str,
    objects: list[dict[str, Any]],
    *,
    warnings: list[dict[str, Any]] | None = None,
) -> DrawingScanSnapshot:
    layer_counts = Counter(str(item.get("layer") or "0") for item in objects)
    type_counts = Counter(str(item.get("entity_type") or item.get("object_name") or item.get("dxftype") or "UNKNOWN") for item in objects)
    return DrawingScanSnapshot(
        source_dwg=source_dwg,
        object_count=len(objects),
        layer_counts=dict(sorted(layer_counts.items())),
        type_counts=dict(sorted(type_counts.items())),
        objects=objects,
        warnings=warnings or [],
    )
