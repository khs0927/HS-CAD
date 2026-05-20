from __future__ import annotations

from src.modifiers.block_modifier import replace_block_plan


def test_replace_block_plan_warns_missing_definition() -> None:
    plan = replace_block_plan(
        [{"entity_type": "INSERT", "name": "D900", "insert": [0, 0, 0], "layer": "A-DOOR"}],
        "D900",
        "D1000",
        layer="A-DOOR",
        known_blocks=["D900"],
    )
    assert plan["count"] == 1
    assert "new block definition missing" in plan["warnings"]
