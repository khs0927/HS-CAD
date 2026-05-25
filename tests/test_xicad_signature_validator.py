from __future__ import annotations

import json
from pathlib import Path

from src.analysis.dxf_delta_extractor import DXFDeltaReport
from src.execution.xicad_signature_validator import validate_signature
from src.workers.xicad_signature_validator_worker import run_signature_validator_worker


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
    assert result["status"] == "empty_delta"
    assert result["promotable"] is False
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
    assert result["status"] == "mismatch"
    assert result["promotable"] is False
    assert "mismatch" in result["reason"].lower()


def test_signature_validator_worker_keeps_failed_results_out_of_verified_file(tmp_path: Path):
    seeds_json = tmp_path / "seeds.json"
    delta_json = tmp_path / "delta.json"
    out_dir = tmp_path / "out"

    seeds_json.write_text(
        json.dumps(
            {
                "seeds": [
                    {
                        "alias": "WAL",
                        "signature_hint": {
                            "expected_layer_names": ["C"],
                            "expected_added_types": ["LINE"],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    delta_json.write_text(
        json.dumps(
            {
                "command_hint": "WAL",
                "added_count": 0,
                "deleted_count": 0,
                "modified_count": 0,
                "added": [],
                "deleted": [],
                "modified": [],
            }
        ),
        encoding="utf-8",
    )

    result = run_signature_validator_worker(
        seeds_json_path=str(seeds_json),
        delta_json_path=str(delta_json),
        out_dir=str(out_dir),
    )

    assert result["status"] == "empty_delta"
    validation_results = json.loads((out_dir / "XICAD_SIGNATURE_VALIDATION_RESULTS.json").read_text(encoding="utf-8"))
    verified_signatures = json.loads((out_dir / "VERIFIED_XICAD_SIGNATURES.json").read_text(encoding="utf-8"))
    assert validation_results["validation_results"][0]["status"] == "empty_delta"
    assert verified_signatures["verified_signatures"] == []
