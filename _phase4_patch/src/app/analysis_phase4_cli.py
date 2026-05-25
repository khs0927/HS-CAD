from __future__ import annotations

import typer

from src.analysis.phase4_metrics_decision_bridge import write_phase4_bridge_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-analysis-phase4-bridge")
def hscad_analysis_phase4_bridge(
    workspace: str = typer.Option("outputs/webhard_batch_100", help="Workspace containing Phase 3 binding artifacts."),
    phase3_report_path: str | None = typer.Option(None, help="Optional explicit PHASE3_REAL_DATA_BINDING_REPORT.json path."),
    out_dir: str | None = typer.Option(None, help="Optional output directory. Defaults to workspace."),
):
    """Create Phase 4 metrics and review-only decision bridge artifacts."""

    result = write_phase4_bridge_outputs(
        workspace,
        phase3_report_path=phase3_report_path,
        out_dir=out_dir,
    )
    console.print(result)
