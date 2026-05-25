from __future__ import annotations

from src.analysis.dxf_delta_extractor import DXFDeltaReport
from src.execution.xicad_signature_validator import validate_signature


def test_validate_signature_success():
    seed = {
        "alias": "WAL",
        "signature_hint": {
            "expected_layer_names": ["0", "C", "xicad_wall"],
            "expected_added_types": ["LINE", "LWPOLYLINE"],
        },
    }
    delta = DXFDeltaReport(
        command_hint="WAL",
        added_count=2,
        deleted_count=0,
        modified_count=0,
        added=[
            {"layer": "C", "entity_type": "LINE", "handle": "A1"},
            {"layer": "0", "entity_type": "LINE", "handle": "A2"},
        ],
        deleted=[],
        modified=[],
    )
    result = validate_signature(seed, delta)
    assert result["status"] == "verified"
    assert "C" in result["evidence"]["matched_layers"]


def test_validate_signature_empty_delta():
    seed = {"alias": "WAL", "signature_hint": {}}
    delta = DXFDeltaReport(
        command_hint="WAL",
        added_count=0,
        deleted_count=0,
        modified_count=0,
        added=[],
        deleted=[],
        modified=[],
    )
    result = validate_signature(seed, delta)
    assert result["status"] == "failed"
    assert "empty" in result["reason"]


def test_validate_signature_mismatch():
    seed = {
        "alias": "WAL",
        "signature_hint": {
            "expected_layer_names": ["xicad_wall"],
            "expected_added_types": ["LINE"],
        },
    }
    delta = DXFDeltaReport(
        command_hint="WAL",
        added_count=1,
        deleted_count=0,
        modified_count=0,
        added=[{"layer": "DIM", "entity_type": "TEXT", "handle": "A1"}],
        deleted=[],
        modified=[],
    )
    result = validate_signature(seed, delta)
    assert result["status"] == "failed"
    assert "mismatch" in result["reason"].lower()
