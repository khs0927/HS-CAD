from __future__ import annotations

import typer

from src.analysis.final_live_runner_safety_spec_gate import write_final_live_runner_safety_spec_gate_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-final-live-runner-safety-spec-gate")
def hscad_final_live_runner_safety_spec_gate(
    repo_root: str = typer.Option(".", help="Repository root."),
    local_validation_summary_json: str = typer.Option("outputs/local_validation_recorder/LOCAL_VALIDATION_RESULT_SUMMARY.json", help="Local validation summary JSON."),
    out_dir: str = typer.Option("outputs/final_live_runner_safety_spec_gate", help="Output directory."),
):
    """Generate final live runner safety spec gate artifacts. Does not implement runner."""

    result = write_final_live_runner_safety_spec_gate_outputs(
        repo_root=repo_root,
        local_validation_summary_json=local_validation_summary_json,
        out_dir=out_dir,
    )
    console.print(result)
