from pathlib import Path

from src.integrations.xicad_rule_engine import (
    XiCadRuleEngine,
    is_binary_or_protected_lisp,
    parse_block_catalog,
    parse_dat_file,
    parse_pgp_aliases,
    parse_shortkeys,
)


def test_xicad_rule_engine_parses_core_text_assets(tmp_path: Path):
    root = tmp_path / "xicad"
    (root / "xiLib").mkdir(parents=True)
    (root / "_ZWCad").mkdir()
    (root / "Lisp").mkdir()
    (root / "Lib" / "Plan_Furniture").mkdir(parents=True)
    (root / "xiLib" / "xiShortkey.key").write_text("INS,xiINSUL,단열재 그리기\nCOL,xiDrawColumn,기둥 그리기\nD1,xiDoor1,외여닫이문\n", encoding="cp949")
    (root / "_ZWCad" / "zwcad.pgp").write_text("A, *ARC\nL, *LINE\nM, *MOVE\n", encoding="cp949")
    (root / "Lisp" / "xiBE_hbe.dat").write_text("H-100x100x6x8,100,100,6,8\nH-200x200x8x12,200,200,8,12\n", encoding="cp949")
    (root / "Lib" / "Plan_Furniture" / "Plan_Furniture_Chair01.dwg").write_bytes(b"dummy")
    (root / "Lisp" / "xiStru.des").write_bytes(b"BWF PROTECTED LISP FILE")

    engine = XiCadRuleEngine(root)
    rules = engine.load_all()
    summary = engine.summarize(rules)

    assert summary["shortkeys"] == 3
    assert summary["pgp_aliases"] == 3
    assert summary["steel_specs"] == 2
    assert summary["block_catalog"] == 1
    assert summary["protected_lisp_files"] == 1
    assert "INS -> xiINSUL" in engine.generate_ai_drafting_prompt(rules)


def test_individual_parsers_are_resilient(tmp_path: Path):
    key = tmp_path / "xiShortkey.key"
    key.write_text("; comment\nA,xiA,설명\nBADLINE\n", encoding="cp949")
    assert parse_shortkeys(key)[0].alias == "A"

    pgp = tmp_path / "zwcad.pgp"
    pgp.write_text("L, *LINE\n", encoding="utf-8")
    assert parse_pgp_aliases(pgp)[0].command == "LINE"

    dat = tmp_path / "xiBE_ang.dat"
    dat.write_text("L-50x50x6,50,50,6\n", encoding="utf-8")
    spec = parse_dat_file(dat)[0]
    assert spec.category == "angle"
    assert spec.values[:3] == [50.0, 50.0, 6.0]

    lib = tmp_path / "Lib"
    (lib / "Elev_Door").mkdir(parents=True)
    (lib / "Elev_Door" / "Elev_DR_01.dwg").write_bytes(b"dwg")
    assert parse_block_catalog(lib)[0].category == "Elev_Door"

    protected = tmp_path / "xiCad.des"
    protected.write_bytes(b"BWF PROTECTED LISP")
    assert is_binary_or_protected_lisp(protected).protected is True
