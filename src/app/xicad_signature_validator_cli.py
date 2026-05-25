from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from src.app.cli import app
from src.workers.xicad_signature_validator_worker import run_signature_validator_worker

console = Console()


@app.command(name="xicad-signature-validate")
def xicad_signature_validate(
    seeds_json: str = typer.Option(..., help="Path to XICAD_SIGNATURE_SEEDS.json"),
    delta_json: str = typer.Option(..., help="Path to extracted delta signature JSON"),
    out_dir: str = typer.Option("outputs/xicad_signatures", help="Output directory for verified signatures"),
):
    """
    Validates a live extracted sandbox Delta against the theoretical Signature Seed.
    """
    console.print("[cyan]Running XiCAD Signature Validator...[/cyan]")
    
    if not Path(seeds_json).exists():
        console.print(f"[red]Error: Seeds JSON not found at {seeds_json}[/red]")
        raise typer.Exit(1)
        
    if not Path(delta_json).exists():
        console.print(f"[red]Error: Delta JSON not found at {delta_json}[/red]")
        raise typer.Exit(1)

    result = run_signature_validator_worker(
        seeds_json_path=seeds_json,
        delta_json_path=delta_json,
        out_dir=out_dir,
    )

    if "error" in result:
        console.print(f"[red]{result['error']}[/red]")
    elif result.get("status") == "verified":
        console.print(f"[green]Validation Passed for alias '{result['alias']}'![/green]")
        console.print(result["evidence"])
    else:
        console.print(f"[yellow]Validation Failed for alias '{result['alias']}':[/yellow]")
        console.print(result["reason"])
