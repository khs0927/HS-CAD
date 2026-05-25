from __future__ import annotations

import typer

from src.analysis.pr55_59_combined_review import write_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-pr55-59-combined-review")
def hscad_pr55_59_combined_review(
    repo_root: str = typer.Option(".", help="Repository root."),
    out_dir: str = typer.Option("outputs/pr55_59_combined_review", help="Output directory."),
):
    """Generate PR #55~#59 combined review package. Does not merge main."""

    result = write_outputs(repo_root=repo_root, out_dir=out_dir)
    console.print(result)
