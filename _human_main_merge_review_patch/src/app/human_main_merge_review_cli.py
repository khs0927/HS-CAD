from __future__ import annotations

import typer

from src.analysis.human_main_merge_review_gate import write_human_main_merge_review_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-human-main-merge-review-gate")
def hscad_human_main_merge_review_gate(
    repo_root: str = typer.Option(".", help="Repository root."),
    post_main_safety_workspace: str = typer.Option("outputs/post_main_local_validation_live_runner_safety", help="Workspace containing PR58/post-main safety artifacts."),
    out_dir: str = typer.Option("outputs/human_main_merge_review_gate", help="Output directory."),
):
    """Generate human main merge review gate artifacts. Does not merge main."""

    result = write_human_main_merge_review_outputs(
        repo_root=repo_root,
        post_main_safety_workspace=post_main_safety_workspace,
        out_dir=out_dir,
    )
    console.print(result)
