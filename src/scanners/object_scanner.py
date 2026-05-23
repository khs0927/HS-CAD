from __future__ import annotations

from typing import Any

from src.cad_core.base import CADAdapter
from src.scanners.boundary_scanner import boundary_summary
from src.scanners.dimension_scanner import dimension_summary


def scan_objects(adapter: CADAdapter) -> list[dict[str, Any]]:
    return adapter.scan_modelspace()


def object_type_counts(objects: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in objects:
        kind = str(item.get('entity_type') or item.get('object_name') or item.get('dxftype') or 'UNKNOWN')
        counts[kind] = counts.get(kind, 0) + 1
    return dict(sorted(counts.items()))


def layer_counts(objects: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in objects:
        layer = str(item.get('layer') or '0')
        counts[layer] = counts.get(layer, 0) + 1
    return dict(sorted(counts.items()))


def scan_evidence_package(adapter: CADAdapter) -> dict[str, Any]:
    """Scan an adapter and return a compact evidence package.

    This keeps future COM/PyRx/ezdxf pipelines aligned around a shared object
    shape before deeper architecture or OCR/vector evidence fusion happens.
    """
    objects = scan_objects(adapter)
    return build_evidence_package(objects, source='cad_adapter')


def build_evidence_package(objects: list[dict[str, Any]], *, source: str = 'objects') -> dict[str, Any]:
    return {
        'source': source,
        'object_count': len(objects),
        'object_type_counts': object_type_counts(objects),
        'layer_counts': layer_counts(objects),
        'boundary_summary': boundary_summary(objects),
        'dimension_summary': dimension_summary(objects),
        'objects': objects,
    }
