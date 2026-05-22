from __future__ import annotations

from src.orchestrator.xicad_contracts import XiCADContractEvidence
from src.orchestrator.xicad_contract_validator import validate_contract_evidence


def test_incomplete_evidence_is_blocked():
    evidence = XiCADContractEvidence(alias="WAL", status="passed")
    result = validate_contract_evidence(evidence)
    assert result.can_promote is False
    assert result.status == "BLOCKED"
    assert "manual_zwcad_version" in result.missing
    assert "observed_prompt_sequence" in result.missing
    assert result.promotion_candidate is None


def test_complete_evidence_creates_candidate_but_autorun_false():
    evidence = XiCADContractEvidence(
        alias="WAL",
        status="passed",
        manual_zwcad_version="ZWCAD 2026",
        xicad_root="C:/XICAD",
        observed_prompt_sequence=("start point", "end point"),
        accepted_argument_pattern=("point", "point"),
        output_observation="wall was created on expected layer",
        rollback_observation="undo restored previous state",
        safety_observation="no save/delete/explode observed",
        no_save_confirmed=True,
        no_delete_confirmed=True,
        no_explode_confirmed=True,
    )
    result = validate_contract_evidence(evidence, evidence_path="WAL_record.json")
    assert result.can_promote is True
    assert result.promotion_candidate is not None
    assert result.promotion_candidate["verified"] is True
    assert result.promotion_candidate["scriptable"] is True
    assert result.promotion_candidate["auto_run_allowed"] is False
    assert result.promotion_candidate["review_required"] is True
