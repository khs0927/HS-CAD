from __future__ import annotations

import typer

from src.analysis.final_todo_integration_readiness import write_final_todo_readiness_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-final-todo-readiness")
def hscad_final_todo_readiness(
    repo_root: str = typer.Option(".", help="Repository root."),
    workspace: str = typer.Option("outputs/webhard_batch_100", help="Workspace containing Phase 3~12 artifacts."),
    out_dir: str = typer.Option("outputs/final_todo_integration_readiness", help="Output directory."),
):
    """Generate final TODO and integration readiness report."""

    result = write_final_todo_readiness_outputs(repo_root=repo_root, workspace=workspace, out_dir=out_dir)
    console.print(result)
