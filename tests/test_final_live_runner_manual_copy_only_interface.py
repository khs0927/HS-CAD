import json

from src.analysis.final_live_runner_manual_copy_only_interface import (
    ManualCopyOnlyInput,
    evaluate_manual_copy_only_interface,
    write_manual_copy_only_interface_outputs,
)


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _valid_preflight_files(tmp_path):
    preflight = _write_json(
        tmp_path / "preflight.json",
        {
            "status": "ready_for_manual_implementation_review",
            "execution_allowed": False,
            "sendcommand_allowed": False,
            "saveas_allowed": False,
            "xicad_alias_execution_allowed": False,
            "original_dwg_mutation_allowed": False,
            "final_live_runner_implemented": False,
        },
    )
    audit = _write_json(tmp_path / "audit.json", {"will_sendcommand": False})
    refusals = _write_json(tmp_path / "refusals.json", {})
    next_plan = _write_json(tmp_path / "next_plan.json", {"implementation_pr_can_start": False})
    return preflight, audit, refusals, next_plan


def _ready_input(tmp_path):
    preflight, audit, refusals, next_plan = _valid_preflight_files(tmp_path)
    return ManualCopyOnlyInput(
        preflight_decision_json=preflight,
        audit_intent_json=audit,
        refusal_reasons_json=refusals,
        next_plan_json=next_plan,
        original_dwg=tmp_path / "original.dwg",
        working_copy_dwg=tmp_path / "copy.dwg",
        save_as_target=tmp_path / "result.dwg",
        manual_live_flag=True,
        operator_approved=True,
    )


def test_manual_copy_interface_blocks_without_preflight(tmp_path):
    decision = evaluate_manual_copy_only_interface(
        ManualCopyOnlyInput(
            preflight_decision_json=tmp_path / "missing.json",
            audit_intent_json=tmp_path / "missing-audit.json",
            refusal_reasons_json=tmp_path / "missing-refusals.json",
            next_plan_json=tmp_path / "missing-next.json",
        )
    )

    assert decision["status"] == "blocked"
    assert decision["execution_allowed"] is False
    assert decision["sendcommand_allowed"] is False
    assert decision["saveas_allowed"] is False
    assert any("preflight_decision_json" in reason for reason in decision["blocked_reasons"])


def test_manual_copy_interface_ready_still_disallows_execution(tmp_path):
    decision = evaluate_manual_copy_only_interface(_ready_input(tmp_path))

    assert decision["status"] == "ready_for_operator_review"
    assert decision["execution_allowed"] is False
    assert decision["sendcommand_allowed"] is False
    assert decision["saveas_allowed"] is False
    assert decision["xicad_alias_execution_allowed"] is False
    assert decision["original_dwg_mutation_allowed"] is False
    assert decision["production_execution_allowed"] is False
    assert decision["safety"]["this_package_runs_cad"] is False


def test_manual_copy_interface_blocks_unsafe_preflight_flag(tmp_path):
    preflight, audit, refusals, next_plan = _valid_preflight_files(tmp_path)
    _write_json(
        preflight,
        {
            "status": "ready_for_manual_implementation_review",
            "execution_allowed": False,
            "sendcommand_allowed": True,
            "saveas_allowed": False,
            "xicad_alias_execution_allowed": False,
            "original_dwg_mutation_allowed": False,
            "final_live_runner_implemented": False,
        },
    )

    decision = evaluate_manual_copy_only_interface(
        ManualCopyOnlyInput(
            preflight_decision_json=preflight,
            audit_intent_json=audit,
            refusal_reasons_json=refusals,
            next_plan_json=next_plan,
            original_dwg=tmp_path / "original.dwg",
            working_copy_dwg=tmp_path / "copy.dwg",
            save_as_target=tmp_path / "result.dwg",
            manual_live_flag=True,
            operator_approved=True,
        )
    )

    assert decision["status"] == "blocked"
    assert "preflight unsafe flag true: sendcommand_allowed" in decision["blocked_reasons"]


def test_manual_copy_interface_writes_review_only_outputs(tmp_path):
    out_dir = tmp_path / "out"
    result = write_manual_copy_only_interface_outputs(_ready_input(tmp_path), out_dir=out_dir)

    assert result["status"] == "ready_for_operator_review"
    assert result["execution_allowed"] is False
    for path_key in [
        "interface_json",
        "interface_md",
        "operator_prompt_md",
        "audit_intent_json",
        "refusal_json",
        "next_pr_json",
    ]:
        assert (out_dir / result[path_key].split(str(out_dir))[-1].lstrip("\\/")).exists()

    payload = json.loads((out_dir / "NEXT_MANUAL_COPY_ONLY_EXECUTION_CANDIDATE_PR.json").read_text(encoding="utf-8"))
    assert payload["can_start"] is False
