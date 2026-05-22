from __future__ import annotations

from neuro_seq_cad.cad.xicad_command_plan import build_xicad_command_plan


def test_command_plan_keeps_dxfbuilder_as_fallback():
    entities = [
        {"id": "wall-1", "type": "wall"},
        {"id": "ins-1", "type": "insulation"},
        {"id": "door-1", "type": "door"},
    ]
    plan = build_xicad_command_plan(entities)
    assert plan["fallback"] == "DXFBuilder remains canonical output"
    assert plan["mode"] == "review_only"
    assert all(command.get("scriptable") is False for command in plan["commands"])
    assert any(command.get("recommended_alias") == "WAL" for command in plan["commands"])
    assert any(command.get("recommended_alias") == "INS" for command in plan["commands"])
