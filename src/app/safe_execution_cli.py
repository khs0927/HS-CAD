from __future__ import annotations

import typer

from src.app.cli import app
from src.app.logger import console
from src.workers.safe_execution_worker import run_safe_execution_dry_run_worker


@app.command("safe-execution-dry-run")
def safe_execution_dry_run(
    command_plan_json: str = typer.Option(..., help="DOMAIN_RULE_COMMAND_PLAN.json path"),
    review_gate_json: str = typer.Option(..., help="DOMAIN_RULE_REVIEW_GATE.json path"),
    signoff_manifest_json: str = typer.Option(..., help="DOMAIN_RULE_SIGNOFF_MANIFEST.json path"),
    out_dir: str = typer.Option("outputs/safe_execution", help="Output directory"),
    original_dwg: str = typer.Option("", help="Original DWG path. Must not be modified."),
    working_copy_dwg: str = typer.Option("", help="Working copy DWG path."),
    save_as_target: str = typer.Option("", help="SaveAs target path for future approved execution."),
):
    result = run_safe_execution_dry_run_worker(
        command_plan_json=command_plan_json,
        review_gate_json=review_gate_json,
        signoff_manifest_json=signoff_manifest_json,
        out_dir=out_dir,
        original_dwg=original_dwg,
        working_copy_dwg=working_copy_dwg,
        save_as_target=save_as_target,
    )
    console.print(result)
