from __future__ import annotations
import typer
from src.app.cli import app
from src.app.logger import console
from src.analysis.phase3_real_data_binding import write_phase3_real_data_binding_outputs

@app.command("hscad-analysis-phase3-bind")
def hscad_analysis_phase3_bind(
    workspace: str = typer.Option("outputs/webhard_batch_100", help="Workspace containing Phase 1/2 derived artifacts."),
    out_dir: str | None = typer.Option(None, help="Optional output directory. Defaults to the workspace."),
):
    result = write_phase3_real_data_binding_outputs(workspace, out_dir=out_dir)
    console.print(result)
