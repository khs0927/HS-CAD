from __future__ import annotations

from src.analysis.dxf_delta_extractor import extract_dxf_delta
from src.execution.scan_snapshot import DrawingScanSnapshot


def test_extract_dxf_delta_detects_changes():
    before = DrawingScanSnapshot(
        source_dwg="test.dwg",
        object_count=2,
        layer_counts={"0": 2},
        type_counts={"LINE": 2},
        objects=[
            {"handle": "A1", "entity_type": "LINE", "layer": "0", "length": 10},
            {"handle": "A2", "entity_type": "LINE", "layer": "0", "length": 20},
        ],
        warnings=[],
    )

    after = DrawingScanSnapshot(
        source_dwg="test.dwg",
        object_count=2,
        layer_counts={"0": 1, "xicad_wall": 1},
        type_counts={"LINE": 2},
        objects=[
            {"handle": "A1", "entity_type": "LINE", "layer": "0", "length": 15},  # Modified
            {"handle": "A3", "entity_type": "LINE", "layer": "xicad_wall", "length": 30},  # Added
        ],
        warnings=[],
    )

    report = extract_dxf_delta(before, after, command_hint="WAL")

    assert report.command_hint == "WAL"
    assert report.added_count == 1
    assert report.deleted_count == 1
    assert report.modified_count == 1

    assert report.added[0]["handle"] == "A3"
    assert report.deleted[0]["handle"] == "A2"
    assert report.modified[0].handle == "A1"
    assert "length" in report.modified[0].changed_keys
    assert report.modified[0].old_state["length"] == 10
    assert report.modified[0].new_state["length"] == 15
