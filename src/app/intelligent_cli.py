from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from src.app.cli import app
from src.app.logger import console, success
from src.orchestrator.intelligent_router import build_intelligent_route


@app.command("hscad-agent-plan")
def hscad_agent_plan(
    task: str = typer.Argument(..., help="Natural-language HS-CAD task."),
    has_image: bool = typer.Option(False, "--has-image", help="Task includes an image/PDF floorplan."),
    has_pdf: bool = typer.Option(False, "--has-pdf", help="Task includes a PDF floorplan."),
    has_dwg: bool = typer.Option(False, "--has-dwg", help="Task includes an existing DWG."),
    has_active_drawing: bool = typer.Option(False, "--active", help="Task uses the active ZWCAD drawing."),
    wants_write: bool = typer.Option(False, "--wants-write", help="Task intends to change a drawing."),
    image: Path | None = typer.Option(None, "--image", help="Optional image/PDF path."),
    dwg: Path | None = typer.Option(None, "--dwg", help="Optional DWG path."),
    out_dir: Path = typer.Option(Path("outputs/agent_route"), "--out-dir", help="Report output directory."),
):
    """Build an intelligent HS-CAD route without modifying drawings."""
    result = build_intelligent_route(
        task,
        has_image=has_image,
        has_pdf=has_pdf,
        has_dwg=has_dwg,
        has_active_drawing=has_active_drawing,
        wants_write=wants_write,
        image_path=image,
        dwg_path=dwg,
        out_dir=out_dir,
    )

    table = Table("#", "Tool", "Command", "Safety")
    for idx, step in enumerate(result.decision.selected_tools, start=1):
        table.add_row(str(idx), str(step.get("tool", "")), str(step.get("command", "")), str(step.get("safety_class", "")))
    console.print(table)

    if result.decision.held_tools:
        held = Table("#", "Held Tool", "Command", "Reason")
        for idx, step in enumerate(result.decision.held_tools, start=1):
            held.add_row(str(idx), str(step.get("tool", "")), str(step.get("command", "")), str(step.get("safety_reason", "")))
        console.print(held)

    if result.decision.warnings:
        console.print({"warnings": result.decision.warnings})
    if result.decision.missing_context:
        console.print({"missing_context": result.decision.missing_context})

    success(f"HS-CAD intelligent route written: {result.report_paths}")


@app.command("hscad-agent-explain")
def hscad_agent_explain(task: str = typer.Argument(..., help="Natural-language HS-CAD task.")):
    """Explain the thinking workflow for a task in a compact form."""
    result = build_intelligent_route(task, out_dir="outputs/agent_explain")
    console.print(result.decision.to_dict())
