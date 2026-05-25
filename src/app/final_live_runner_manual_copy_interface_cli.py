from __future__ import annotations

import typer

from src.analysis.final_live_runner_manual_copy_only_interface import (
    ManualCopyOnlyInput,
    write_manual_copy_only_interface_outputs,
)
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-final-live-runner-manual-copy-interface")
def hscad_final_live_runner_manual_copy_interface(
    preflight_decision_json: str = typer.Option("outputs/final_live_runner_preflight_guard/FINAL_LIVE_RUNNER_PREFLIGHT_DECISION.json", help="Preflight decision JSON."),
    audit_intent_json: str = typer.Option("outputs/final_live_runner_preflight_guard/FINAL_LIVE_RUNNER_PREFLIGHT_AUDIT_INTENT.json", help="Preflight audit intent JSON."),
    refusal_reasons_json: str = typer.Option("outputs/final_live_runner_preflight_guard/FINAL_LIVE_RUNNER_PREFLIGHT_REFUSAL_REASONS.json", help="Preflight refusal reasons JSON."),
    next_plan_json: str = typer.Option("outputs/final_live_runner_preflight_guard/NEXT_IMPLEMENTATION_PR_PLAN.json", help="Preflight next plan JSON."),
    original_dwg: str = typer.Option("C:/cad/test/original.dwg", help="Original DWG path. This command never mutates it."),
    working_copy_dwg: str = typer.Option("C:/cad/test_work/copy.dwg", help="Working copy DWG path."),
    save_as_target: str = typer.Option("C:/cad/test_work/result.dwg", help="SaveAs target path. This command does not SaveAs."),
    operator_name: str = typer.Option("human-reviewer", help="Human operator name for the prompt."),
    manual_live_flag: bool = typer.Option(False, "--manual-live-flag/--no-manual-live-flag", help="Explicit manual live flag."),
    operator_approved: bool = typer.Option(False, "--operator-approved/--no-operator-approved", help="Explicit operator approval."),
    out_dir: str = typer.Option("outputs/final_live_runner_manual_copy_only_interface", help="Output directory."),
) -> None:
    """Create a dry-run manual copy-only operator interface without executing CAD."""

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
    result = write_manual_copy_only_interface_outputs(inp, out_dir=out_dir)
    console.print(result)
