from __future__ import annotations

from src.execution.xicad_signature_matcher import match_signatures_in_objects


def test_match_verified_wal_signature_finds_parallel_line_pair():
    objects = [
        {"handle": "10", "layer": "C", "entity_type": "LINE", "start": [0, 0], "end": [4000, 0]},
        {"handle": "11", "layer": "C", "entity_type": "LINE", "start": [0, 200], "end": [4000, 200]},
        {"handle": "12", "layer": "TEXT", "entity_type": "TEXT"},
    ]
    signatures = [
        {
            "alias": "WAL",
            "status": "verified",
            "evidence": {
                "matched_layers": ["C"],
                "matched_types": ["LINE"],
            },
        }
    ]

    result = match_signatures_in_objects(objects, signatures)

    assert result["status"] == "review_required"
    assert result["match_count"] == 1
    assert result["matches"][0]["alias"] == "WAL"
    assert result["matches"][0]["entity_handles"] == ["10", "11"]
    assert result["matches"][0]["evidence"]["distance"] == 200.0
    assert result["safety"]["cad_mutation"] is False


def test_matcher_skips_when_no_verified_signatures_are_available():
    result = match_signatures_in_objects(
        [{"handle": "10", "layer": "C", "entity_type": "LINE", "start": [0, 0], "end": [1, 0]}],
        [{"alias": "WAL", "status": "empty_delta"}],
    )

    assert result["match_count"] == 0
    assert "No verified signatures" in result["warnings"][0]
