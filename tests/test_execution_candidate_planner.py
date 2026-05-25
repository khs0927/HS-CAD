from __future__ import annotations

import json
from pathlib import Path

from src.analysis.execution_candidate_planner import (
    READY,
    ExecutionCandidatePlannerInput,
    evaluate_execution_candidate_plan,
    write_execution_candidate_planner_outputs,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_fixture(tmp_path: Path) -> ExecutionCandidatePlannerInput:
    preflight = tmp_path / "preflight.json"
    manual = tmp_path / "manual.json"
    oda = tmp_path / "oda.json"
    write_json(preflight, {
        "status": "ready_for_manual_implementation_review",
        "execution_allowed": False,
        "sendcommand_allowed": False,
        "saveas_allowed": False,
        "original_dwg_mutation_allowed": False,
        "xicad_alias_execution_allowed": False,
        "final_live_runner_implemented": False,
    })
    write_json(manual, {
        "status": "ready_for_operator_review",
        "execution_allowed": False,
        "sendcommand_allowed": False,
        "saveas_allowed": False,
        "original_dwg_mutation_allowed": False,
        "xicad_alias_execution_allowed": False,
        "production_execution_allowed": False,
    })
    write_json(oda, {
        "status": "converted",
        "original_mutated": False,
        "converted_dxf_path": "outputs/oda_conversion_contract/copy.dxf",
        "log_path": "outputs/oda_conversion_contract/log.txt",
    })
    return ExecutionCandidatePlannerInput(
        preflight_decision_json=preflight,
        manual_copy_interface_json=manual,
        oda_conversion_contract_json=oda,
        operator_approved=True,
        manual_live_flag=True,
        operator_name="tester",
    )


def test_ready_fixture_still_keeps_action_flags_false(tmp_path: Path) -> None:
    decision = evaluate_execution_candidate_plan(make_fixture(tmp_path))
    assert decision["status"] == READY
    assert decision["execution_candidate_allowed"] is False
    assert decision["sendcommand_allowed"] is False
    assert decision["saveas_allowed"] is False
    assert decision["original_dwg_mutation_allowed"] is False
    assert decision["xicad_alias_execution_allowed"] is False


def test_blocks_missing_preflight(tmp_path: Path) -> None:
    inp = make_fixture(tmp_path)
    inp = ExecutionCandidatePlannerInput(**{**inp.__dict__, "preflight_decision_json": tmp_path / "missing.json"})
    decision = evaluate_execution_candidate_plan(inp)
    assert decision["status"] == "blocked"


def test_blocks_preflight_not_ready(tmp_path: Path) -> None:
    inp = make_fixture(tmp_path)
    write_json(Path(inp.preflight_decision_json), {"status": "blocked"})
    decision = evaluate_execution_candidate_plan(inp)
    assert decision["status"] == "blocked"


def test_blocks_manual_interface_not_ready(tmp_path: Path) -> None:
    inp = make_fixture(tmp_path)
    write_json(Path(inp.manual_copy_interface_json), {"status": "blocked"})
    decision = evaluate_execution_candidate_plan(inp)
    assert decision["status"] == "blocked"


def test_blocks_oda_uncertain_original_mutation(tmp_path: Path) -> None:
    inp = make_fixture(tmp_path)
    write_json(Path(inp.oda_conversion_contract_json), {"status": "converted", "original_mutated": None})
    decision = evaluate_execution_candidate_plan(inp)
    assert decision["status"] == "blocked"


def test_writer_creates_outputs(tmp_path: Path) -> None:
    result = write_execution_candidate_planner_outputs(make_fixture(tmp_path), out_dir=tmp_path / "out")
    assert Path(result["decision_json"]).exists()
    assert Path(result["decision_md"]).exists()
    assert Path(result["candidate_steps_json"]).exists()
    assert Path(result["rollback_json"]).exists()
    assert Path(result["audit_json"]).exists()
    assert Path(result["refusal_json"]).exists()
    assert result["execution_candidate_allowed"] is False
