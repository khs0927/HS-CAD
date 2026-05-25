from __future__ import annotations

from src.execution.entity_delta import build_entity_delta
from src.execution.xicad_signature_candidate import build_signature_candidate


def test_wal_like_delta_builds_parallel_line_signature_candidate():
    before = []
    after = [
        {"handle": "10", "layer": "WAL", "entity_type": "LINE", "start": [0, 0], "end": [5000, 0]},
        {"handle": "11", "layer": "WAL", "entity_type": "LINE", "start": [0, 200], "end": [5000, 200]},
    ]

    delta = build_entity_delta(before, after)
    candidate = build_signature_candidate("WAL", delta)
    payload = candidate.to_dict()

    assert payload["alias"] == "WAL"
    assert payload["status"] == "candidate"
    assert payload["requires_human_review"] is True
    assert payload["safety"]["original_dwg_mutation"] is False
    assert payload["observed_delta"]["added_type_counts"]["LINE"] == 2
    assert payload["geometry_patterns"][0]["kind"] == "parallel_line_pair"
    assert payload["geometry_patterns"][0]["evidence"][0]["distance"] == 200


def test_empty_delta_candidate_remains_low_confidence_and_review_required():
    delta = build_entity_delta([], [])
    candidate = build_signature_candidate("COL", delta)

    assert candidate.confidence == 0.0
    assert candidate.requires_human_review is True
    assert "No added entities were observed." in candidate.warnings
