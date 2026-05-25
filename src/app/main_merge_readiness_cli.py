from __future__ import annotations

import typer

from src.analysis.main_merge_readiness_decision import write_main_merge_decision_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-main-merge-readiness-decision")
def hscad_main_merge_readiness_decision(
    repo_root: str = typer.Option(".", help="Repository root."),
    post_pr53_workspace: str = typer.Option("outputs/post_pr53_main_merge_local_validation", help="Workspace containing Post-PR53 artifacts."),
    out_dir: str = typer.Option("outputs/main_merge_readiness_decision", help="Output directory."),
):
    """Generate main merge readiness decision artifacts. Does not merge main."""

    result = write_main_merge_decision_outputs(
        repo_root=repo_root,
        post_pr53_workspace=post_pr53_workspace,
        out_dir=out_dir,
    )
    console.print(result)
