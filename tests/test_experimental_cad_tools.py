from __future__ import annotations

from src.adapters.backend_registry import build_default_backend_registry
from src.scanners.boundary_scanner import boundary_summary, closed_polyline_candidates
from src.scanners.dimension_scanner import dimension_summary, extract_dimensions
from src.scanners.object_scanner import build_evidence_package, layer_counts, object_type_counts


SYNTHETIC_OBJECTS = [
    {
        'object_name': 'AcDbPolyline',
        'entity_type': 'POLYLINE',
        'closed': True,
        'points': [[0, 0], [10, 0], [10, 5], [0, 5]],
        'layer': 'WAL1',
    },
    {
        'object_name': 'AcDbAlignedDimension',
        'entity_type': 'DIMENSION',
        'layer': 'DIM',
        'measurement': 3000,
        'text_override': '3000',
    },
    {
        'object_name': 'AcDbText',
        'entity_type': 'TEXT',
        'layer': 'ROOM-TEXT',
        'text': 'ROOM 101',
    },
]


def test_backend_registry_classifies_planned_backends_without_importing_runtimes():
    registry = build_default_backend_registry()
    rows = registry.to_dict()['backends']
    names = {row['name'] for row in rows}

    assert 'ZWCAD COM/ActiveX' in names
    assert 'PyRx/cad-pyrx' in names
    assert 'pyzwcad compatibility shim' in names
    assert 'ezdxf offline DXF' in names
    assert any(row['default'] is True and row['status'] == 'stable-default' for row in rows)
    assert any(row['status'] == 'experimental' for row in rows)


def test_backend_registry_search_finds_large_drawing_backend():
    registry = build_default_backend_registry()
    rows = registry.find('large drawings')

    assert any(row.adapter_class == 'PyRxAdapter' for row in rows)


def test_boundary_scanner_adds_area_bbox_and_confidence():
    candidates = closed_polyline_candidates(SYNTHETIC_OBJECTS)

    assert len(candidates) == 1
    assert candidates[0]['bbox'] == [0, 0, 10, 5]
    assert candidates[0]['area'] == 50
    assert candidates[0]['candidate_type'] == 'closed_polyline_boundary'
    assert candidates[0]['confidence'] > 0.8


def test_boundary_summary_returns_rollup_and_candidates():
    summary = boundary_summary(SYNTHETIC_OBJECTS)

    assert summary['candidate_count'] == 1
    assert summary['total_candidate_area'] == 50
    assert len(summary['candidates']) == 1


def test_dimension_scanner_extracts_measured_evidence():
    dimensions = extract_dimensions(SYNTHETIC_OBJECTS)

    assert len(dimensions) == 1
    assert dimensions[0]['candidate_type'] == 'dimension_evidence'
    assert dimensions[0]['dimension_kind'] == 'aligned'
    assert dimensions[0]['value'] == 3000
    assert dimensions[0]['text'] == '3000'


def test_dimension_summary_groups_by_kind():
    summary = dimension_summary(SYNTHETIC_OBJECTS)

    assert summary['dimension_count'] == 1
    assert summary['measured_count'] == 1
    assert summary['by_kind'] == {'aligned': 1}


def test_object_scanner_builds_backend_neutral_evidence_package():
    package = build_evidence_package(SYNTHETIC_OBJECTS, source='synthetic')

    assert package['source'] == 'synthetic'
    assert package['object_count'] == 3
    assert package['object_type_counts']['POLYLINE'] == 1
    assert package['layer_counts']['WAL1'] == 1
    assert package['boundary_summary']['candidate_count'] == 1
    assert package['dimension_summary']['dimension_count'] == 1


def test_object_count_helpers_are_stable():
    assert object_type_counts(SYNTHETIC_OBJECTS) == {'DIMENSION': 1, 'POLYLINE': 1, 'TEXT': 1}
    assert layer_counts(SYNTHETIC_OBJECTS) == {'DIM': 1, 'ROOM-TEXT': 1, 'WAL1': 1}
