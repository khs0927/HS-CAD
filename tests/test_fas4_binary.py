from pathlib import Path

import pytest

from xicad_mcp.fas4_binary import Fas4Error, parse_fas4


def test_rejects_non_fas4(tmp_path: Path) -> None:
    path = tmp_path / "bad.fas"
    path.write_bytes(b"not fas")
    with pytest.raises(Fas4Error):
        parse_fas4(path)


def test_parses_minimal_header(tmp_path: Path) -> None:
    # Empty bytecode/resource is valid inspection input even though it is not executable.
    payload = b"1 $"
    data = b"\r\n FAS4-FILE ; Do not change it!\r\n" + str(len(payload)).encode() + b"\r\n" + payload
    path = tmp_path / "minimal.fas"
    path.write_bytes(data)
    module = parse_fas4(path)
    assert module.symbol_slots == 1
    assert module.bytecode_size == 0
    assert module.command_entrypoints == ()
