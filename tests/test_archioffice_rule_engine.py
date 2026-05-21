from pathlib import Path

from src.integrations.archioffice_rule_engine import (
    ArchiOfficeRuleEngine,
    parse_archioffice_block_catalog,
    parse_onekey_lisp,
    parse_room_names,
    parse_shape_steel,
    parse_xpress_pgp,
)


def test_archioffice_rule_engine_parses_core_assets(tmp_path: Path):
    root = tmp_path / "ArchiOfficeZW2024"
    (root / "InerCAD" / "Library" / "Furniture").mkdir(parents=True)
    (root / "XPress").mkdir()
    (root / "InerCAD" / "onekey.lsp").write_text(
        ";;;  C:PM     Position Mark\n(defun C:TB () (princ))\n",
        encoding="cp949",
    )
    (root / "InerCAD" / "ShapeSteel.txt").write_text(
        "*H-Beam\nH-100x100x6x8 100 100 6 8\n*Square Pipe\nP-100x50x3 100 50 3\n",
        encoding="cp949",
    )
    (root / "XPress" / "XPRESS.PGP").write_text("XBM, *XBEAM\nXEL, *XELEV\n", encoding="cp949")
    (root / "InerCAD" / "ROOMNAME.TXT").write_text("OFFICE\nWAREHOUSE\n", encoding="cp949")
    (root / "InerCAD" / "Library" / "Furniture" / "Chair01.dwg").write_bytes(b"dwg")

    engine = ArchiOfficeRuleEngine(root)
    rules = engine.load_all()
    summary = engine.summarize(rules)

    assert summary["onekey_commands"] == 2
    assert summary["xpress_aliases"] == 2
    assert summary["steel_specs"] == 2
    assert summary["room_names"] == 2
    assert summary["block_catalog"] == 1
    assert "ARCHIOFFICE RULE ENGINE" in engine.generate_ai_drafting_prompt(rules)


def test_archioffice_individual_parsers_are_resilient(tmp_path: Path):
    lisp = tmp_path / "onekey.lsp"
    lisp.write_text(";;;  C:AA     Draw Something\n(defun C:BB () (princ))\n", encoding="utf-8")
    assert [entry.alias for entry in parse_onekey_lisp(lisp)] == ["AA", "BB"]

    pgp = tmp_path / "XPRESS.PGP"
    pgp.write_text("XBM, *XBEAM\n", encoding="utf-8")
    assert parse_xpress_pgp(pgp)[0].command == "XBEAM"

    steel = tmp_path / "ShapeSteel.txt"
    steel.write_text("*H-Beam\nH-200x200x8x12,200,200,8,12\n", encoding="utf-8")
    spec = parse_shape_steel(steel)[0]
    assert spec.category == "H-Beam"
    assert spec.values == [200.0, 200.0, 8.0, 12.0]

    rooms = tmp_path / "ROOMNAME.TXT"
    rooms.write_text("; comment\nROOM-1\n", encoding="utf-8")
    assert parse_room_names(rooms) == ["ROOM-1"]

    lib = tmp_path / "Library"
    (lib / "Door").mkdir(parents=True)
    (lib / "Door" / "D01.dwg").write_bytes(b"dwg")
    assert parse_archioffice_block_catalog(lib)[0].category == "Door"

