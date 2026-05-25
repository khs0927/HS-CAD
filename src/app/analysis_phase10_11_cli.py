from __future__ import annotations

import typer

from src.analysis.phase10_domain_decision_connector import write_phase10_outputs
from src.analysis.phase11_copied_dwg_validation_bridge import write_phase11_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-analysis-phase10-11-domain-copy")
def hscad_analysis_phase10_11_domain_copy(
    workspace: str = typer.Option("outputs/webhard_batch_100", help="Workspace containing Phase 8/9 artifacts."),
    original_dwg: str | None = typer.Option(None, help="Optional original DWG path for plan-only validation."),
    working_copy_dwg: str | None = typer.Option(None, help="Optional working copy DWG path for plan-only validation."),
    save_as_target: str | None = typer.Option(None, help="Optional save-as target path for plan-only validation."),
    out_dir: str | None = typer.Option(None, help="Optional output directory. Defaults to workspace."),
):
    """Create Phase 10~11 review-only domain and copied-DWG validation bridge artifacts."""

    target = out_dir or workspace
    phase10 = write_phase10_outputs(workspace, out_dir=target)
    phase11 = write_phase11_outputs(
        workspace,
        phase10_connector_path=f"{target}/PHASE10_DOMAIN_DECISION_CONNECTOR.json",
        original_dwg=original_dwg,
        working_copy_dwg=working_copy_dwg,
        save_as_target=save_as_target,
        out_dir=target,
    )
    console.print({"phase10": phase10, "phase11": phase11})
