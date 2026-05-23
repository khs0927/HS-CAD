from __future__ import annotations

from typing import Any


def _is_dimension(item: dict[str, Any]) -> bool:
    object_name = str(item.get('object_name') or item.get('entity_type') or '').lower()
    return 'dim' in object_name or item.get('entity_type') == 'DIMENSION'


def _dimension_kind(item: dict[str, Any]) -> str:
    object_name = str(item.get('object_name') or item.get('entity_type') or '').lower()
    if 'aligned' in object_name:
        return 'aligned'
    if 'rotated' in object_name or 'linear' in object_name:
        return 'linear'
    if 'radius' in object_name or 'radial' in object_name:
        return 'radius'
    if 'diameter' in object_name:
        return 'diameter'
    if 'angle' in object_name or 'angular' in object_name:
        return 'angular'
    return 'dimension'


def extract_dimensions(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract dimension-like evidence rows from scanned CAD objects."""
    rows: list[dict[str, Any]] = []
    for item in objects:
        if not _is_dimension(item):
            continue
        row = dict(item)
        row['candidate_type'] = 'dimension_evidence'
        row['dimension_kind'] = _dimension_kind(item)
        row['value'] = item.get('measurement')
        row['text'] = item.get('text_override') or item.get('text') or item.get('TextString')
        row['confidence'] = 1.0 if item.get('measurement') is not None else 0.7
        rows.append(row)
    return rows


def dimension_summary(objects: list[dict[str, Any]]) -> dict[str, Any]:
    dimensions = extract_dimensions(objects)
    by_kind: dict[str, int] = {}
    measured_count = 0
    for item in dimensions:
        kind = str(item.get('dimension_kind') or 'dimension')
        by_kind[kind] = by_kind.get(kind, 0) + 1
        if item.get('value') is not None:
            measured_count += 1
    return {
        'dimension_count': len(dimensions),
        'measured_count': measured_count,
        'by_kind': by_kind,
        'dimensions': dimensions,
    }
