from __future__ import annotations

import json
from pathlib import Path

from src.orchestrator.xicad_contract_test_plan import create_contract_test_plan
from src.orchestrator.xicad_contract_report import load_and_summarize_contracts


def test_create_contract_test_plan(tmp_path: Path):
    paths = create_contract_test_plan("WAL,D1,W1", tmp_path)
    assert Path(paths["json"]).exists()
    assert Path(paths["markdown"]).exists()

    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert payload["auto_execution"] is False
    aliases = {item["alias"] for item in payload["contracts"]}
    assert aliases == {"WAL", "D1", "W1"}


def test_contract_summary(tmp_path: Path):
    paths = create_contract_test_plan("WAL,D1", tmp_path)
    summary = load_and_summarize_contracts(paths["json"])
    assert summary["contract_count"] == 2
    assert summary["verified_count"] == 0
    assert summary["scriptable_count"] == 0
    assert summary["auto_execution"] is False
