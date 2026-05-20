from __future__ import annotations

from src.reports.debug_bundle import collect_debug_bundle


class FakeAdapter:
    warnings = []

    def scan_modelspace(self):
        return [{"entity_type": "TEXT", "layer": "A-ROOM", "text": "사무실"}]


def test_collect_debug_bundle_without_zwcad(tmp_path):
    paths = collect_debug_bundle(FakeAdapter(), "sample.dwg", None, tmp_path, max_objects=1)
    assert (tmp_path / "environment.json").exists()
    assert (tmp_path / "scan_sample.json").exists()
    assert (tmp_path / "debug_summary.md").exists()
    assert "environment" in paths
