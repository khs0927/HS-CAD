from pathlib import Path

from src.integrations.archioffice_rule_engine import ArchiOfficeRuleEngine
from src.integrations.xicad_rule_engine import XiCadRuleEngine
from src.modifiers.architectural_modifier import (
    create_steel_beam_actions,
    create_xicad_wall_actions,
    insert_spec_block_actions,
)


def test_create_xicad_wall_actions_uses_wall_style_offsets(tmp_path: Path):
    root = tmp_path / "xicad"
    (root / "xiLib").mkdir(parents=True)
    (root / "xiLib" / "xiDrawWall.txt").write_text("basic,-75,75,A-WALL\n", encoding="utf-8")

    actions = create_xicad_wall_actions(XiCadRuleEngine(root), "basic", 5000, origin=(100, 100, 0))

    assert len(actions) == 2
    assert actions[0]["action"] == "create_polyline"
    assert actions[0]["layer"] == "A-WALL"
    assert actions[0]["points"][0] == [100.0, 25.0, 0.0]
    assert actions[0]["points"][1] == [5100.0, 25.0, 0.0]


def test_create_steel_beam_actions_from_xicad_dat(tmp_path: Path):
    root = tmp_path / "xicad"
    (root / "Lisp").mkdir(parents=True)
    (root / "Lisp" / "xiBE_hbe.dat").write_text("H-200x200x8x12,200,200,8,12\n", encoding="utf-8")

    actions = create_steel_beam_actions(XiCadRuleEngine(root), True, "h_beam", "200x200", origin=(0, 0, 0))

    assert len(actions) == 1
    assert actions[0]["closed"] is True
    assert actions[0]["layer"] == "A-BEAM-STEEL"
    assert len(actions[0]["points"]) == 13


def test_create_steel_beam_actions_from_archioffice_shape_table(tmp_path: Path):
    root = tmp_path / "ArchiOfficeZW2024"
    (root / "InerCAD").mkdir(parents=True)
    (root / "InerCAD" / "ShapeSteel.txt").write_text("*Square Pipe\nP-100x50x3,100,50,3\n", encoding="utf-8")

    actions = create_steel_beam_actions(ArchiOfficeRuleEngine(root), False, "Square", "100x50", origin=(10, 10, 0))

    assert len(actions) == 1
    assert actions[0]["closed"] is True
    assert actions[0]["source"] == "archioffice_rule_engine"
    assert len(actions[0]["points"]) == 5


def test_insert_spec_block_actions_maps_safe_layers(tmp_path: Path):
    root = tmp_path / "xicad"
    (root / "xiLib").mkdir(parents=True)
    (root / "xiLib" / "xiBlkLayerSet.txt").write_text("Furniture,SYM-FURN,3,Continuous\n", encoding="utf-8")

    xicad_action = insert_spec_block_actions(XiCadRuleEngine(root), True, "Furniture", "CHAIR_01")[0]
    ao_action = insert_spec_block_actions(ArchiOfficeRuleEngine(tmp_path / "missing"), False, "Landscape", "TREE_01")[0]

    assert xicad_action["layer"] == "A-SYM-SYM-FURN"
    assert ao_action["layer"] == "A-AO-SYM-LANDSCAPE"
    assert xicad_action["action"] == ao_action["action"] == "insert_block"

