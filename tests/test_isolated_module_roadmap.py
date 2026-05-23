from __future__ import annotations

import importlib


def test_isolated_adapter_modules_import_without_optional_runtime_dependencies():
    """Roadmap modules must remain safe to keep before full integration.

    These modules are intentionally retained as future backend hooks. Importing
    them should not require optional CAD runtimes such as PyRx, pyzwcad, ezdxf,
    COM, or an active CAD application.
    """
    for module_name in (
        "src.adapters.pyrx_adapter",
        "src.adapters.pyzwcad_adapter",
        "src.adapters.ezdxf_adapter",
    ):
        importlib.import_module(module_name)


def test_isolated_scanner_helpers_import_without_cad_runtime():
    """Scanner helpers should stay pure and reusable by future workers/CLIs."""
    for module_name in (
        "src.scanners.boundary_scanner",
        "src.scanners.dimension_scanner",
        "src.scanners.object_scanner",
    ):
        importlib.import_module(module_name)


def test_scanner_helper_contracts_on_synthetic_objects():
    boundary_scanner = importlib.import_module("src.scanners.boundary_scanner")
    dimension_scanner = importlib.import_module("src.scanners.dimension_scanner")

    objects = [
        {
            "object_name": "AcDbPolyline",
            "closed": True,
            "points": [[0, 0], [10, 0], [10, 5], [0, 5]],
            "layer": "WAL1",
        },
        {
            "object_name": "AcDbAlignedDimension",
            "layer": "DIM",
            "measurement": 3000,
        },
        {
            "object_name": "AcDbText",
            "text": "ROOM",
        },
    ]

    boundaries = boundary_scanner.closed_polyline_candidates(objects)
    dimensions = dimension_scanner.extract_dimensions(objects)

    assert len(boundaries) == 1
    assert boundaries[0]["bbox"]["min_x"] == 0
    assert boundaries[0]["bbox"]["min_y"] == 0
    assert boundaries[0]["bbox"]["max_x"] == 10
    assert boundaries[0]["bbox"]["max_y"] == 5
    assert len(dimensions) == 1
    assert dimensions[0]["measurement"] == 3000
