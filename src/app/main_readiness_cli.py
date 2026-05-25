from __future__ import annotations

import typer

from src.analysis.main_readiness_local_validation_planner import write_main_readiness_plan_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-main-readiness-plan")
def hscad_main_readiness_plan(
    repo_root: str = typer.Option(".", help="Repository root."),
    final_review_workspace: str = typer.Option("outputs/final_review_pipeline_verify", help="Workspace containing final review artifacts."),
    out_dir: str = typer.Option("outputs/main_readiness_local_validation", help="Output directory."),
):
    """Generate main-readiness and local-only validation planning artifacts."""

    result = write_main_readiness_plan_outputs(
        repo_root=repo_root,
        final_review_workspace=final_review_workspace,
        out_dir=out_dir,
    )
    console.print(result)
