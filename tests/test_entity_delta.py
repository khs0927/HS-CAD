from __future__ import annotations

from src.execution.entity_delta import build_entity_delta


def test_entity_delta_splits_added_removed_changed_and_unchanged():
    before = [
        {"handle": "1", "layer": "WALL", "entity_type": "LINE", "start": [0, 0], "end": [10, 0]},
        {"handle": "2", "layer": "TEXT", "entity_type": "TEXT", "text": "A"},
        {"handle": "3", "layer": "OLD", "entity_type": "CIRCLE", "center": [0, 0], "radius": 1},
    ]
    after = [
        {"handle": "1", "layer": "WALL", "entity_type": "LINE", "start": [0, 0], "end": [10, 0]},
        {"handle": "2", "layer": "TEXT", "entity_type": "TEXT", "text": "B"},
        {"handle": "4", "layer": "WALL", "entity_type": "LINE", "start": [0, 1], "end": [10, 1]},
    ]

    report = build_entity_delta(before, after)

    assert report.summary["added_count"] == 1
    assert report.summary["removed_count"] == 1
    assert report.summary["changed_count"] == 1
    assert report.unchanged_count == 1
    assert report.changed[0].changed_fields == ["text"]


def test_entity_delta_uses_geometry_fingerprint_when_handle_is_missing():
    before = [{"layer": "WALL", "entity_type": "LINE", "start": [0, 0], "end": [10, 0]}]
    after = [
        {"layer": "WALL", "entity_type": "LINE", "start": [0, 0], "end": [10, 0]},
        {"layer": "WALL", "entity_type": "LINE", "start": [0, 1], "end": [10, 1]},
    ]

    report = build_entity_delta(before, after)

    assert report.summary["added_count"] == 1
    assert report.summary["unchanged_count"] == 1
    assert report.added[0].entity["start"] == [0, 1]
