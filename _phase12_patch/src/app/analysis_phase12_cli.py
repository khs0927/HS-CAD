from __future__ import annotations

import typer

from src.analysis.phase12_manual_live_execution_candidate import write_phase12_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-analysis-phase12-manual-live-candidate")
def hscad_analysis_phase12_manual_live_candidate(
    workspace: str = typer.Option("outputs/webhard_batch_100", help="Workspace containing Phase 11 plan artifacts."),
    phase11_plan_path: str | None = typer.Option(None, help="Optional PHASE11_COPY_VALIDATION_CLI_PLAN.json path."),
    allowlist_plan_path: str | None = typer.Option(None, help="Optional XICAD_ALIAS_ALLOWLIST_PLAN.json path."),
    alias: str = typer.Option("WAL", help="XiCAD alias candidate."),
    manual_live_flag: bool = typer.Option(False, help="Must be true to create a manual-ready candidate."),
    operator_approved: bool = typer.Option(False, help="Must be true to create a manual-ready candidate."),
    out_dir: str | None = typer.Option(None, help="Optional output directory. Defaults to workspace."),
):
    """Create Phase 12 manual-only live execution candidate artifacts. Does not execute CAD."""

    result = write_phase12_outputs(
        workspace,
        phase11_plan_path=phase11_plan_path,
        allowlist_plan_path=allowlist_plan_path,
        alias=alias,
        manual_live_flag=manual_live_flag,
        operator_approved=operator_approved,
        out_dir=out_dir,
    )
    console.print(result)
