from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from src.app.cli import app
from src.workers.xicad_signature_matcher_worker import run_signature_matcher_worker

console = Console()


@app.command(name="xicad-signature-match")
def xicad_signature_match(
    snapshot_json: str = typer.Option(..., help="Path to scan snapshot JSON"),
    signatures_json: str = typer.Option(..., help="Path to verified signature JSON"),
    out_dir: str = typer.Option("outputs/xicad_signature_matches", help="Output directory"),
):
    """
    Finds review-required XiCAD signature matches in a scan snapshot.
    """
    if not Path(snapshot_json).exists():
        console.print(f"[red]Error: snapshot JSON not found at {snapshot_json}[/red]")
        raise typer.Exit(1)
    if not Path(signatures_json).exists():
        console.print(f"[red]Error: signatures JSON not found at {signatures_json}[/red]")
        raise typer.Exit(1)

    result = run_signature_matcher_worker(
        snapshot_json=snapshot_json,
        signatures_json=signatures_json,
        out_dir=out_dir,
    )
    console.print(result)
