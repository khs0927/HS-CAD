from __future__ import annotations

from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import success
from src.xicad_automation.models import WorkflowSpec


@app.command("xicad-bg-approve")
def xicad_bg_approve(
    workflow: Path = typer.Option(..., "--workflow"),
    out: Path | None = typer.Option(None, "--out"),
    confirm: str = typer.Option(..., "--confirm", help="Must be exactly LIVE-XICAD"),
):
    """Set live mode and bind approval to the exact workflow contents."""
    if confirm != "LIVE-XICAD":
        raise typer.BadParameter("Live approval requires --confirm LIVE-XICAD")
    spec = WorkflowSpec.model_validate_json(workflow.read_text(encoding="utf-8"))
    spec.dry_run = False
    spec.approval_token = spec.expected_approval_token()
    destination = out or workflow
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
    success(f"Approved exact XiCAD workflow: {destination}")
