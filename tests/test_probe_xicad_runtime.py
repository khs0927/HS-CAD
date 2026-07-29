from pathlib import Path

from scripts.probe_xicad_runtime import _aliases, _lisp_string


def test_alias_parser_matches_frozen_inventory() -> None:
    aliases = _aliases(Path(__file__).parent / "fixtures" / "xiShortkey.357.key")
    assert len(aliases) == 357
    assert len({alias.casefold() for alias in aliases}) == 357
    assert aliases[0] == "CT"


def test_lisp_string_normalizes_windows_path() -> None:
    assert _lisp_string(r'C:\xicad\Lisp\"quoted".zelx') == 'C:/xicad/Lisp/\\"quoted\\".zelx'
