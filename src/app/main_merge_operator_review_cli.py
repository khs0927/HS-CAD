from __future__ import annotations

import typer

from src.analysis.main_merge_operator_review import write_main_merge_operator_review_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-main-merge-operator-review")
def hscad_main_merge_operator_review(
    repo_root: str = typer.Option(".", help="Repository root."),
    pr56_workspace: str = typer.Option("outputs/pr55_main_ready_review_only_validation", help="Workspace containing PR56 validation artifacts."),
    out_dir: str = typer.Option("outputs/main_merge_operator_review", help="Output directory."),
):
    """Generate main merge operator review artifacts. Does not merge main."""

    result = write_main_merge_operator_review_outputs(
        repo_root=repo_root,
        pr56_workspace=pr56_workspace,
        out_dir=out_dir,
    )
    console.print(result)
