from __future__ import annotations

import json
from pathlib import Path

from src.analysis.execution_candidate_planner import ExecutionCandidatePlannerInput, evaluate_execution_candidate_plan, write_execution_candidate_planner_outputs


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_input(tmp_path: Path) -> ExecutionCandidatePlannerInput:
    preflight = tmp_path / "preflight.json"
    manual = tmp_path / "manual.json"
    oda = tmp_path / "oda.json"
    write_json(preflight, {"status": "ready_for_manual_implementation_review"})
    write_json(manual, {"status": "ready_for_operator_review"})
    write_json(oda, {"status": "converted", "original_mutated": False})
    return ExecutionCandidatePlannerInput(
        preflight_decision_json=preflight,
        manual_copy_interface_json=manual,
        oda_conversion_contract_json=oda,
        operator_approved=True,
        manual_live_flag=True,
    )


def test_ready_status_keeps_action_flags_false(tmp_path: Path) -> None:
    result = evaluate_execution_candidate_plan(make_input(tmp_path))
    assert result["status"] == "ready_for_human_review"
    assert result["execution_candidate_allowed"] is False
    assert result["sendcommand_allowed"] is False
    assert result["saveas_allowed"] is False
    assert result["original_dwg_mutation_allowed"] is False
    assert result["xicad_alias_execution_allowed"] is False


def test_missing_evidence_blocks(tmp_path: Path) -> None:
    inp = make_input(tmp_path)
    inp = ExecutionCandidatePlannerInput(**{**inp.__dict__, "preflight_decision_json": tmp_path / "missing.json"})
    result = evaluate_execution_candidate_plan(inp)
    assert result["status"] == "blocked"


def test_writer_creates_review_outputs(tmp_path: Path) -> None:
    result = write_execution_candidate_planner_outputs(make_input(tmp_path), out_dir=tmp_path / "out")
    assert Path(result["decision_json"]).exists()
    assert Path(result["decision_md"]).exists()
    assert Path(result["candidate_steps_json"]).exists()
    assert Path(result["rollback_json"]).exists()
    assert Path(result["audit_json"]).exists()
    assert Path(result["refusal_json"]).exists()
