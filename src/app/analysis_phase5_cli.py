from __future__ import annotations

import typer

from src.analysis.phase5_domain_rule_decision_bridge import write_phase5_bridge_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-analysis-phase5-domain-bridge")
def hscad_analysis_phase5_domain_bridge(
    workspace: str = typer.Option("outputs/webhard_batch_100", help="Workspace containing Phase 4 bridge artifacts."),
    phase4_package_path: str | None = typer.Option(None, help="Optional explicit PHASE4_DECISION_BRIDGE_PACKAGE.json path."),
    out_dir: str | None = typer.Option(None, help="Optional output directory. Defaults to workspace."),
):
    """Create Phase 5 review-only Domain Rule Decision input artifacts."""

    result = write_phase5_bridge_outputs(
        workspace,
        phase4_package_path=phase4_package_path,
        out_dir=out_dir,
    )
    console.print(result)
