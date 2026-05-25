from __future__ import annotations

import typer

from src.analysis.local_validation_recorder_final_runner_safety import write_local_validation_recorder_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-local-validation-recorder")
def hscad_local_validation_recorder(
    repo_root: str = typer.Option(".", help="Repository root."),
    result_dir: str = typer.Option("outputs/local_validation_results", help="Directory containing manual local validation result JSON files."),
    out_dir: str = typer.Option("outputs/local_validation_recorder", help="Output directory."),
    create_templates: bool = typer.Option(True, help="Create empty result templates."),
):
    """Record manual local validation results. Does not execute CAD."""

    result = write_local_validation_recorder_outputs(
        repo_root=repo_root,
        result_dir=result_dir,
        out_dir=out_dir,
        create_templates=create_templates,
    )
    console.print(result)
