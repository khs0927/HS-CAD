from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.final_live_runner_manual_copy_only_interface import (
    ManualCopyOnlyInput,
    write_manual_copy_only_interface_outputs,
)


def run(
    *,
    preflight_decision_json: str | Path = "outputs/final_live_runner_preflight_guard/FINAL_LIVE_RUNNER_PREFLIGHT_DECISION.json",
    audit_intent_json: str | Path = "outputs/final_live_runner_preflight_guard/FINAL_LIVE_RUNNER_PREFLIGHT_AUDIT_INTENT.json",
    refusal_reasons_json: str | Path = "outputs/final_live_runner_preflight_guard/FINAL_LIVE_RUNNER_PREFLIGHT_REFUSAL_REASONS.json",
    next_plan_json: str | Path = "outputs/final_live_runner_preflight_guard/NEXT_IMPLEMENTATION_PR_PLAN.json",
    original_dwg: str | Path = "C:/cad/test/original.dwg",
    working_copy_dwg: str | Path = "C:/cad/test_work/copy.dwg",
    save_as_target: str | Path = "C:/cad/test_work/result.dwg",
    operator_name: str = "human-reviewer",
    manual_live_flag: bool = False,
    operator_approved: bool = False,
    out_dir: str | Path = "outputs/final_live_runner_manual_copy_only_interface",
    **_: Any,
) -> dict[str, Any]:
    inp = ManualCopyOnlyInput(
        preflight_decision_json=preflight_decision_json,
        audit_intent_json=audit_intent_json,
        refusal_reasons_json=refusal_reasons_json,
        next_plan_json=next_plan_json,
        original_dwg=original_dwg,
        working_copy_dwg=working_copy_dwg,
        save_as_target=save_as_target,
        operator_name=operator_name,
        manual_live_flag=manual_live_flag,
        operator_approved=operator_approved,
    )
    return write_manual_copy_only_interface_outputs(inp, out_dir=out_dir)


def run_worker(**kwargs: Any) -> dict[str, Any]:
    return run(**kwargs)
