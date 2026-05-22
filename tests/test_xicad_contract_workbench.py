from __future__ import annotations

import json
from pathlib import Path

from src.orchestrator.xicad_contract_workbench import write_contract_session, write_review_matrix


def test_write_contract_session(tmp_path: Path):
    paths = write_contract_session("WAL", tmp_path)
    assert Path(paths["json"]).exists()
    assert Path(paths["markdown"]).exists()
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert payload["alias"] == "WAL"
    assert payload["function"] == "xiDrawWall"
    assert "no_save_confirmed" in payload["required_evidence_fields"]


def test_write_review_matrix(tmp_path: Path):
    paths = write_review_matrix("WAL,D1,W1", tmp_path)
    assert Path(paths["json"]).exists()
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert payload["aliases"] == ["WAL", "D1", "W1"]
    assert len(payload["sessions"]) == 3
