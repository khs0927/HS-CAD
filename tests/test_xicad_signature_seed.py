from __future__ import annotations

from src.execution.xicad_signature_seed import build_signature_seeds_from_rules


def test_build_signature_seeds_from_wall_and_opening_rules():
    rules = {
        "wall_styles": {
            "Group01": {
                "total_thickness": 200.0,
                "lines": [
                    {"offset": 0, "layer": "WAL", "color": 1},
                    {"offset": 200, "layer": "WAL", "color": 1},
                ],
            }
        },
        "config_variables": {
            "xiDoor1": {"default_width": 900.0},
            "xiWin1": {"default_width": 1200.0},
        },
        "block_layer_rules": {},
    }

    seeds = build_signature_seeds_from_rules(rules)
    by_alias = {seed.alias: seed for seed in seeds}

    assert by_alias["WAL"].signature_hint["geometry_patterns"][0]["kind"] == "parallel_line_pair"
    assert by_alias["WAL"].signature_hint["thickness_candidates"] == [200.0]
    assert by_alias["D1"].signature_hint["width_candidates"] == [900.0]
    assert by_alias["W1"].signature_hint["width_candidates"] == [1200.0]
    assert all(seed.requires_human_review for seed in seeds)
