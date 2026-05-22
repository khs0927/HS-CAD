from __future__ import annotations

from src.orchestrator.xicad_contracts import build_default_contracts, default_contract_for_alias


def test_default_contracts_are_default_deny():
    contracts = build_default_contracts(["WAL", "INS", "AE", "LC"])
    assert contracts
    for contract in contracts:
        assert contract.verified is False
        assert contract.scriptable is False
        assert contract.auto_run_allowed is False
        assert contract.status.value == "UNVERIFIED"


def test_default_contract_metadata():
    wal = default_contract_for_alias("WAL")
    assert wal.function == "xiDrawWall"
    assert wal.category == "DRAW_ARCH"
    be = default_contract_for_alias("BE")
    assert be.function == "xiBE"
    assert be.category == "DRAW_STRUCT"
