from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.execution_candidate_planner import ExecutionCandidatePlannerInput, write_execution_candidate_planner_outputs


def run(
    *,
    preflight_decision_json: str | Path = "outputs/final_live_runner_preflight_guard/FINAL_LIVE_RUNNER_PREFLIGHT_DECISION.json",
    manual_copy_interface_json: str | Path = "outputs/final_live_runner_manual_copy_only_interface/FINAL_LIVE_RUNNER_MANUAL_COPY_ONLY_INTERFACE.json",
    oda_conversion_contract_json: str | Path = "outputs/oda_conversion_contract/ODA_CONVERSION_CONTRACT.json",
    operator_approved: bool = False,
    manual_live_flag: bool = False,
    operator_name: str = "human-reviewer",
    out_dir: str | Path = "outputs/execution_candidate_planner",
    **_: Any,
) -> dict[str, Any]:
    inp = ExecutionCandidatePlannerInput(
        preflight_decision_json=preflight_decision_json,
        manual_copy_interface_json=manual_copy_interface_json,
        oda_conversion_contract_json=oda_conversion_contract_json,
        operator_approved=operator_approved,
        manual_live_flag=manual_live_flag,
        operator_name=operator_name,
    )
    return write_execution_candidate_planner_outputs(inp, out_dir=out_dir)


def run_worker(**kwargs: Any) -> dict[str, Any]:
    return run(**kwargs)
