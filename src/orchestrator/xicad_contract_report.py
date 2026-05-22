from __future__ import annotations

from pathlib import Path
from typing import Any
import json


def summarize_contract_payload(payload: dict[str, Any]) -> dict[str, Any]:
    contracts = payload.get("contracts", [])
    by_status: dict[str, int] = {}
    verified_count = 0
    scriptable_count = 0
    for contract in contracts:
        status = str(contract.get("status", "UNKNOWN"))
        by_status[status] = by_status.get(status, 0) + 1
        if contract.get("verified"):
            verified_count += 1
        if contract.get("scriptable"):
            scriptable_count += 1
    return {
        "contract_count": len(contracts),
        "by_status": by_status,
        "verified_count": verified_count,
        "scriptable_count": scriptable_count,
        "auto_execution": bool(payload.get("auto_execution", False)),
    }


def load_and_summarize_contracts(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return summarize_contract_payload(payload)
