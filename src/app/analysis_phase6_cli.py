from __future__ import annotations

import typer

from src.analysis.phase6_domain_rule_workflow_adapter import write_phase6_adapter_outputs
from src.app.cli import app
from src.app.logger import console


@app.command("hscad-analysis-phase6-domain-adapter")
def hscad_analysis_phase6_domain_adapter(
    workspace: str = typer.Option("outputs/webhard_batch_100", help="Workspace containing Phase 5 domain bridge artifacts."),
    phase5_package_path: str | None = typer.Option(None, help="Optional explicit PHASE5_DOMAIN_RULE_INPUT_PACKAGE.json path."),
    out_dir: str | None = typer.Option(None, help="Optional output directory. Defaults to workspace."),
):
    """Create Phase 6 review-only Domain Rule Workflow adapter artifacts."""

    result = write_phase6_adapter_outputs(
        workspace,
        phase5_package_path=phase5_package_path,
        out_dir=out_dir,
    )
    console.print(result)
