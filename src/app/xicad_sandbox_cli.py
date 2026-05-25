from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from src.app.cli import app
from src.execution.xicad_sandbox_runner import XiCADSandboxRunner

console = Console()


@app.command(name="xicad-sandbox-extract")
def xicad_sandbox_extract(
    template_dwg: str = typer.Option(..., help="Path to blank template DWG file"),
    command_hint: str = typer.Option(..., help="Command alias to run (e.g. WAL)"),
    input_sequence: str = typer.Option(..., help="Command inputs to send. Use \\n for enter."),
    out_dir: str = typer.Option("outputs/xicad_signatures", help="Output directory for signatures"),
    delay: float = typer.Option(1.0, help="Delay seconds after SendCommand before snapshot"),
):
    """
    Extracts the geometric delta (signature) of a XiCAD command by executing it in a sandbox ZWCAD.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    working_copy = out / f"sandbox_{command_hint}.dwg"
    sig_file = out / f"{command_hint}_signature.json"

    console.print(f"[cyan]Initializing ZWCAD COM to extract signature for: {command_hint}[/cyan]")
    
    adapter = ZWCADCOMAdapter()
    adapter.connect()

    runner = XiCADSandboxRunner(adapter)

    console.print(f"[yellow]Sending sequence: {repr(input_sequence)}[/yellow]")
    
    delta_report = runner.extract_signature(
        sandbox_dwg_template=template_dwg,
        working_dwg_path=str(working_copy),
        command_hint=command_hint,
        input_sequence=input_sequence,
        delay_seconds=delay,
    )

    with open(sig_file, "w", encoding="utf-8") as f:
        json.dump(delta_report.to_dict(), f, indent=2, ensure_ascii=False)

    console.print(f"[green]Delta successfully extracted![/green]")
    console.print(f"- Added: {delta_report.added_count}")
    console.print(f"- Modified: {delta_report.modified_count}")
    console.print(f"- Deleted: {delta_report.deleted_count}")
    console.print(f"Signature saved to: {sig_file}")
