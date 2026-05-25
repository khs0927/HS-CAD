from __future__ import annotations

import typer

from src.analysis.pr55_main_ready_review_only_validator import write_pr55_validation_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-pr55-main-ready-validation")
def hscad_pr55_main_ready_validation(
    repo_root: str = typer.Option(".", help="Repository root."),
    out_dir: str = typer.Option("outputs/pr55_main_ready_review_only_validation", help="Output directory."),
):
    """Generate PR55 main-ready review-only validation artifacts. Does not merge main."""

    result = write_pr55_validation_outputs(repo_root=repo_root, out_dir=out_dir)
    console.print(result)
