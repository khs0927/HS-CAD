from __future__ import annotations

from pathlib import Path

import typer
from rich.panel import Panel

from src.app.cli import app
from src.app.logger import console, success, warn
from src.orchestrator.xicad_manual_recorder import (
    build_record_command_example,
    write_manual_evidence_and_validation,
    write_manual_record_template,
)


@app.command("xicad-contract-record-template")
def xicad_contract_record_template(
    alias: str = typer.Option(..., "--alias", help="XiCAD alias, e.g. WAL."),
    out: Path = typer.Option(Path("outputs/xicad_contracts/record_template.json"), "--out", help="Output JSON template."),
):
    """Write a manual observation record template.

    This does not control ZWCAD or run XiCAD.
    """
    path = write_manual_record_template(alias, out)
    success(f"Manual record template written: {path}")


@app.command("xicad-contract-record-command")
def xicad_contract_record_command(
    alias: str = typer.Option(..., "--alias", help="XiCAD alias, e.g. WAL."),
):
    """Print a ready-to-edit xicad-contract-record command example."""
    console.print(Panel(build_record_command_example(alias), title=f"{alias.upper()} record command example"))


@app.command("xicad-contract-wizard")
def xicad_contract_wizard(
    alias: str = typer.Option(..., "--alias", help="XiCAD alias, e.g. WAL."),
    out_dir: Path = typer.Option(Path("outputs/xicad_contracts"), "--out-dir", help="Output directory."),
):
    """Interactively record a manual XiCAD contract observation.

    This command asks questions only. It does not run XiCAD, SendCommand, save,
    delete, explode, or modify any drawing.
    """
    alias = alias.upper()
    warn("This wizard does NOT execute XiCAD. Enter only what you manually observed in ZWCAD.")
    answers = {
        "status": typer.prompt("Status (passed/failed)", default="failed"),
        "manual_zwcad_version": typer.prompt("ZWCAD version", default=""),
        "xicad_version": typer.prompt("XiCAD version, if known", default=""),
        "xicad_root": typer.prompt("XiCAD root", default="C:/XICAD"),
        "observed_prompt_sequence": typer.prompt("Observed prompt sequence separated by |", default=""),
        "accepted_argument_pattern": typer.prompt("Accepted argument pattern separated by |", default=""),
        "output_observation": typer.prompt("Output observation", default=""),
        "rollback_observation": typer.prompt("Rollback/undo observation", default=""),
        "safety_observation": typer.prompt("Safety observation", default=""),
        "no_save_confirmed": typer.confirm("Confirm no Save occurred?", default=False),
        "no_delete_confirmed": typer.confirm("Confirm no Delete occurred?", default=False),
        "no_explode_confirmed": typer.confirm("Confirm no Explode occurred?", default=False),
        "notes": typer.prompt("Notes", default=""),
    }
    paths = write_manual_evidence_and_validation(alias, answers, out_dir)
    console.print(paths)
    success("Manual evidence and validation result written.")
