from __future__ import annotations

import typer

from src.analysis.execution_candidate_planner import ExecutionCandidatePlannerInput, write_execution_candidate_planner_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-execution-candidate-planner")
def hscad_execution_candidate_planner(
    preflight_decision_json: str = typer.Option("outputs/final_live_runner_preflight_guard/FINAL_LIVE_RUNNER_PREFLIGHT_DECISION.json"),
    manual_copy_interface_json: str = typer.Option("outputs/final_live_runner_manual_copy_only_interface/FINAL_LIVE_RUNNER_MANUAL_COPY_ONLY_INTERFACE.json"),
    oda_conversion_contract_json: str = typer.Option("outputs/oda_conversion_contract/ODA_CONVERSION_CONTRACT.json"),
    operator_approved: bool = typer.Option(False, "--operator-approved/--no-operator-approved"),
    manual_live_flag: bool = typer.Option(False, "--manual-live-flag/--no-manual-live-flag"),
    operator_name: str = typer.Option("human-reviewer"),
    out_dir: str = typer.Option("outputs/execution_candidate_planner"),
) -> None:
    inp = ExecutionCandidatePlannerInput(
        preflight_decision_json=preflight_decision_json,
        manual_copy_interface_json=manual_copy_interface_json,
        oda_conversion_contract_json=oda_conversion_contract_json,
        operator_approved=operator_approved,
        manual_live_flag=manual_live_flag,
        operator_name=operator_name,
    )
    console.print(write_execution_candidate_planner_outputs(inp, out_dir=out_dir))
