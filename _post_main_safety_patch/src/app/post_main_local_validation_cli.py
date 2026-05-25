from __future__ import annotations

import typer

from src.analysis.post_main_local_validation_live_runner_safety import write_post_main_bundle_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-post-main-local-validation-plan")
def hscad_post_main_local_validation_plan(
    repo_root: str = typer.Option(".", help="Repository root."),
    operator_review_workspace: str = typer.Option("outputs/main_merge_operator_review", help="Workspace containing operator review artifacts."),
    out_dir: str = typer.Option("outputs/post_main_local_validation_live_runner_safety", help="Output directory."),
):
    """Generate post-main local validation and final live runner safety planning artifacts."""

    result = write_post_main_bundle_outputs(
        repo_root=repo_root,
        operator_review_workspace=operator_review_workspace,
        out_dir=out_dir,
    )
    console.print(result)
