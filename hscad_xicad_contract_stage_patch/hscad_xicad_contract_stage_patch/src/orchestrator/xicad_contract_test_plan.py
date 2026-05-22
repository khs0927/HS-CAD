from __future__ import annotations

from pathlib import Path
from .xicad_contracts import build_default_contracts, write_contract_plan


def create_contract_test_plan(aliases: str | list[str] | tuple[str, ...], out_dir: str | Path) -> dict[str, str]:
    if isinstance(aliases, str):
        alias_list = [part.strip().upper() for part in aliases.split(",") if part.strip()]
    else:
        alias_list = [str(alias).strip().upper() for alias in aliases if str(alias).strip()]
    contracts = build_default_contracts(alias_list)
    return write_contract_plan(contracts, out_dir)
