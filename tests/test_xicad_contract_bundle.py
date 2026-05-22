from __future__ import annotations

from pathlib import Path

from src.orchestrator.xicad_contracts import XiCADContractEvidence, write_evidence
from src.orchestrator.xicad_contract_bundle import validate_contract_bundle


def test_validate_contract_bundle_counts_blocked_and_promotable(tmp_path: Path):
    records = tmp_path / "records"
    records.mkdir()
    write_evidence(XiCADContractEvidence(alias="WAL", status="failed"), records / "WAL_record.json")
    write_evidence(
        XiCADContractEvidence(
            alias="D1",
            status="passed",
            manual_zwcad_version="ZWCAD 2026",
            xicad_root="C:/XICAD",
            observed_prompt_sequence=("p1",),
            accepted_argument_pattern=("point",),
            output_observation="door created",
            rollback_observation="undo ok",
            safety_observation="safe",
            no_save_confirmed=True,
            no_delete_confirmed=True,
            no_explode_confirmed=True,
        ),
        records / "D1_record.json",
    )
    paths = validate_contract_bundle(records, tmp_path / "bundle")
    assert Path(paths["json"]).exists()
    text = Path(paths["json"]).read_text(encoding="utf-8")
    assert '"promotable_count": 1' in text
    assert '"blocked_count": 1' in text
