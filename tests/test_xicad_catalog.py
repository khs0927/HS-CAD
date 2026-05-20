from pathlib import Path
from src.integrations.xicad_command_catalog import parse_xicad_shortkey, filter_architecture_commands


def test_parse_xicad_shortkey(tmp_path: Path):
    p = tmp_path / "xiShortkey_origin.key"
    p.write_text("*SecDraw\nWAL ;xiDrawWall ;벽 그리기\nCOL ;xiDrawColumn ;기둥그리기\n", encoding="utf-8")
    rows = parse_xicad_shortkey(p)
    assert len(rows) == 2
    assert rows[0].alias == "WAL"
    assert rows[0].function == "xiDrawWall"


def test_filter_architecture_commands(tmp_path: Path):
    p = tmp_path / "xiShortkey_origin.key"
    p.write_text("*SecDraw\nWAL ;xiDrawWall ;벽 그리기\nABC ;xiOther ;기타\n", encoding="utf-8")
    rows = filter_architecture_commands(parse_xicad_shortkey(p))
    assert [r.alias for r in rows] == ["WAL"]
