from pathlib import Path

from src.orchestrator.xicad_config_parser import (
    parse_layer_setting,
    parse_xiblock_layer_set,
    parse_xidraw_wall,
)
from src.orchestrator.xicad_recipe_registry import get_xicad_recipe, is_scriptable_xicad_command
from src.orchestrator.xicad_taxonomy import (
    build_xicad_prompt_context,
    build_xicad_taxonomy,
    parse_xicad_shortkey,
    search_xicad_commands,
)


def _write_cp949(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("cp949"))


def test_xicad_taxonomy_parses_searches_and_classifies_risk(tmp_path: Path):
    key = tmp_path / "Lisp" / "xiShortkey_origin.key"
    _write_cp949(
        key,
        "\n".join(
            [
                "*SecDraw",
                "WAL ; xiDrawWall ; 벽체 그리기",
                "INS ; xiInsul ; 단열재 그리기",
                "*SecLayer",
                "ABX ; xiAllBlockExplode ; 블록 폭파",
            ]
        ),
    )

    rows = parse_xicad_shortkey(key)
    assert [row.alias for row in rows] == ["WAL", "INS", "ABX"]
    assert rows[0].category == "DRAW_ARCH"
    assert rows[2].risk == "BLOCKED"

    taxonomy = build_xicad_taxonomy(tmp_path)
    matches = search_xicad_commands("벽체 단열", category="DRAW_ARCH", taxonomy=taxonomy)
    assert {match.alias for match in matches} == {"INS", "WAL"}

    context = build_xicad_prompt_context("단열", xicad_root=tmp_path)
    assert "INS" in context
    assert "Do not fabricate" in context


def test_xicad_config_parsers_read_core_files(tmp_path: Path):
    wall = tmp_path / "xiDrawWall.txt"
    _write_cp949(wall, "*****A: 외벽\n0;A-WALL;1;Continuous\n200;A-WALL-IN;2;Hidden\n")
    wall_rows = parse_xidraw_wall(wall)
    assert wall_rows["A (외벽)"][1]["offset"] == 200
    assert wall_rows["A (외벽)"][1]["linetype"] == "Hidden"

    block = tmp_path / "xiBlkLayerSet.txt"
    _write_cp949(block, "DOOR ; A-DOOR ; Continuous ; 3 ; 문\n")
    block_rows = parse_xiblock_layer_set(block)
    assert block_rows["DOOR"]["layer"] == "A-DOOR"
    assert block_rows["DOOR"]["color"] == 3

    layers = tmp_path / "Layer_Setting.lay"
    _write_cp949(layers, "A-WALL,1,Continuous,0.30\n")
    layer_rows = parse_layer_setting(layers)
    assert layer_rows["A-WALL"]["lineweight"] == "0.30"


def test_xicad_recipe_registry_marks_only_verified_scriptable_commands():
    assert is_scriptable_xicad_command("INS") is False
    assert is_scriptable_xicad_command("AE") is False
    assert is_scriptable_xicad_command("LC") is False
    assert is_scriptable_xicad_command("WAL") is False
    assert get_xicad_recipe("ins").function == "xiInsul"
