from __future__ import annotations

from src.reports.architecture_report import generate_drawing_audit, write_architecture_report


def sample_objects():
    return [
        {"entity_type": "LINE", "layer": "A-WALL", "color": 256, "linetype": "ByLayer"},
        {"entity_type": "INSERT", "layer": "A-DOOR", "name": "D900", "insert": [0, 0, 0], "rotation": 0, "x_scale": 1, "y_scale": 1, "z_scale": 1},
        {"entity_type": "TEXT", "layer": "A-ROOM", "text": "사무실 12.5㎡", "insert": [1, 1, 0]},
        {"entity_type": "POLYLINE", "layer": "A-BOUNDARY", "closed": True, "points": [[0, 0], [1, 0], [1, 1], [0, 1]]},
    ]


def test_generate_drawing_audit_detects_architecture_candidates():
    audit = generate_drawing_audit(sample_objects())
    assert audit["object_count"] == 4
    assert "A-WALL" in audit["layers"]["counts"]
    assert audit["blocks"]["candidates"]["door"] == ["D900"]
    assert audit["texts"]["area_candidates"]
    assert audit["polylines"]["closed_count"] == 1


def test_write_architecture_report(tmp_path):
    paths = write_architecture_report(sample_objects(), tmp_path)
    assert (tmp_path / "architecture_summary.json").exists()
    assert (tmp_path / "architecture_summary.md").exists()
    assert (tmp_path / "quantity.xlsx").exists()
    assert "objects" in paths
