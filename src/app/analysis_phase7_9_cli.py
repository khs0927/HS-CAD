from __future__ import annotations

import typer

from src.analysis.phase7_domain_decision_package_bridge import write_phase7_outputs
from src.analysis.phase8_review_gate_chain_bridge import write_phase8_outputs
from src.analysis.phase9_pipeline_readiness_summary import write_phase9_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-analysis-phase7-9-review-bundle")
def hscad_analysis_phase7_9_review_bundle(
    workspace: str = typer.Option("outputs/webhard_batch_100", help="Workspace containing Phase 6 input artifacts."),
    out_dir: str | None = typer.Option(None, help="Optional output directory. Defaults to workspace."),
):
    target = out_dir or workspace
    phase7 = write_phase7_outputs(workspace, out_dir=target)
    phase8 = write_phase8_outputs(workspace, phase7_package_path=f"{target}/PHASE7_DOMAIN_DECISION_PACKAGE.json", out_dir=target)
    phase9 = write_phase9_outputs(target, out_dir=target)
    console.print({"phase7": phase7, "phase8": phase8, "phase9": phase9})
