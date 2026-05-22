from __future__ import annotations

from pathlib import Path
import json

import typer
from rich.table import Table

from src.app.cli import app
from src.app.logger import console, success
from src.orchestrator.autopilot_runner import run_autopilot


@app.command("hscad-auto")
def hscad_auto(
    task: str = typer.Argument(..., help="Natural-language task."),
    mode: str = typer.Option("auto", "--mode", help="auto, general, floorplan, contract, dwg_review"),
    aliases: str = typer.Option("WAL,D1,W1,INS,COL,BE", "--aliases", help="Comma-separated XiCAD aliases."),
    out_dir: Path = typer.Option(Path("outputs/autopilot"), "--out-dir", help="Output directory."),
    has_image: bool = typer.Option(False, "--has-image", help="Task includes image/PDF input."),
    has_dwg: bool = typer.Option(False, "--has-dwg", help="Task includes DWG input."),
    synthetic: bool = typer.Option(False, "--synthetic", help="Use synthetic/safe self-test where supported."),
    run_safe: bool = typer.Option(False, "--run-safe/--plan-only", help="Run safe file/report steps only."),
):
    """Run the HS-CAD safe autopilot planner.

    This command never performs drawing mutation, Save, Delete, Purge, Explode,
    SendCommand, or recipe_registry modification.
    """
    payload = run_autopilot(
        task,
        mode=mode,
        aliases=aliases,
        out_dir=out_dir,
        has_image=has_image,
        has_dwg=has_dwg,
        synthetic=synthetic,
        run_safe=run_safe,
    )
    table = Table("Step Type", "Count")
    table.add_row("executed", str(len(payload.get("executed_steps", []))))
    table.add_row("held", str(len(payload.get("held_steps", []))))
    console.print(table)
    console.print(payload.get("outputs", {}))
    success("HS-CAD autopilot completed.")


@app.command("hscad-auto-contract")
def hscad_auto_contract(
    aliases: str = typer.Option("WAL,D1,W1,INS,COL,BE", "--aliases", help="Comma-separated XiCAD aliases."),
    out_dir: Path = typer.Option(Path("outputs/autopilot_contract"), "--out-dir", help="Output directory."),
    run_safe: bool = typer.Option(True, "--run-safe/--plan-only", help="Run safe setup steps."),
):
    """Prepare XiCAD contract verification workflow automatically."""
    payload = run_autopilot(
        "XiCAD contract verification setup",
        mode="contract",
        aliases=aliases,
        out_dir=out_dir,
        run_safe=run_safe,
    )
    console.print(payload.get("outputs", {}))
    success("HS-CAD contract autopilot completed.")


@app.command("hscad-auto-report")
def hscad_auto_report(
    result: Path = typer.Argument(..., help="autopilot_result.json path."),
):
    """Summarize an existing autopilot result JSON."""
    payload = json.loads(result.read_text(encoding="utf-8"))
    table = Table("Field", "Value")
    table.add_row("task", str(payload.get("task", "")))
    table.add_row("mode", str(payload.get("mode", "")))
    table.add_row("run_safe", str(payload.get("run_safe", False)))
    table.add_row("executed_steps", str(len(payload.get("executed_steps", []))))
    table.add_row("held_steps", str(len(payload.get("held_steps", []))))
    console.print(table)
