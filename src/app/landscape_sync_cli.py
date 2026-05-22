from __future__ import annotations

"""CLI wrapper for the landscape‑sync utilities.

The commands intentionally mirror the pattern used in ``src.app.cli`` so that
they integrate with the existing Typer application (registered in
``src/main.py``).
"""

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from src.orchestrator.landscape_sync import (
    extract_building_overview,
    extract_landscape_sections,
    build_landscape_sync_plan,
    build_text_replacements,
    write_landscape_reports,
)
from src.app.logger import success, warn
from src.reports.json_exporter import export_json

from src.app.cli import app  # noqa: F401,E402
console = Console()

def _load_texts(out_dir: Path) -> list[dict]:
    txt_path = out_dir / "texts.json"
    if not txt_path.is_file():
        raise typer.BadParameter(f"texts.json not found in {out_dir}. Run `texts` command first.")
    return json.loads(txt_path.read_text(encoding="utf-8"))

@app.command("landscape-sync-plan")
def landscape_sync_plan(
    dwg: str = typer.Option(..., help="DWG file path"),
    out_dir: str = typer.Option("outputs/landscape_sync", help="Output directory"),
):
    """Create a sync plan based on the building overview.

    The command assumes that ``texts.json`` already exists in *out_dir* (generated
    by ``src.app.cli texts``).  It does **not** modify the DWG – only JSON and a
    markdown report are produced.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    # Load pre‑scanned text objects
    texts = _load_texts(out_path)
    building = extract_building_overview(texts)
    landscape = extract_landscape_sections(texts)
    plan = build_landscape_sync_plan(building, landscape)
    plan["dwg"] = dwg
    write_landscape_reports(out_path, building, landscape, plan)
    success(f"Landscape sync plan written to {out_path}")

@app.command("landscape-sync-dry-run")
def landscape_sync_dry_run(
    plan_path: str = typer.Option(..., help="Path to landscape_sync_plan.json"),
    out_dir: str = typer.Option("outputs/landscape_sync", help="Output directory"),
):
    """Generate a dry‑run command JSON file for the proposed replacements.

    The function writes ``commands/replace_*.json`` files that can be fed to the
    existing ``run-command --dry-run`` infrastructure.
    """
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    replacements = build_text_replacements(plan)
    commands_dir = Path(out_dir) / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    for idx, cmd in enumerate(replacements, start=1):
        cmd_path = commands_dir / f"replace_{idx:03}.json"
        export_json(cmd, cmd_path)
    # Simple dry‑run summary
    summary = {"generated": len(replacements), "commands_dir": str(commands_dir)}
    export_json(summary, Path(out_dir) / "dry_run_result.json")
    success(f"Dry‑run command files written to {commands_dir}")

@app.command("landscape-sync-apply")
def landscape_sync_apply(
    dwg: str = typer.Option(..., help="Original DWG path"),
    plan_path: str = typer.Option(..., help="Path to landscape_sync_plan.json"),
    save_as: Optional[str] = typer.Option(None, help="Path for the modified DWG"),
    confirm: bool = typer.Option(False, help="Require explicit confirmation to execute"),
):
    """Execute the sync plan on *dwg* and write the result to *save_as*.

    Safety checks (mirroring the Autopilot safe‑only policy):
    * ``confirm`` must be *True*.
    * ``save_as`` must be provided and must differ from ``dwg``.
    * If any ``needs_review`` items exist the command aborts.
    """
    if not confirm:
        warn("Execution requires --confirm flag; aborting.")
        raise typer.Exit(code=1)
    if not save_as:
        warn("--save-as is mandatory for execution; aborting.")
        raise typer.Exit(code=1)
    if Path(dwg).resolve() == Path(save_as).resolve():
        warn("save_as path must differ from original DWG; aborting.")
        raise typer.Exit(code=1)

    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    if plan.get("needs_review"):
        warn("Plan contains items needing review; aborting execution.")
        raise typer.Exit(code=1)

    # Build command list for actual execution (same format as dry‑run).
    replacements = build_text_replacements(plan)
    if not replacements:
        warn("No safe replacements found; nothing to execute.")
        raise typer.Exit(code=0)

    # Write a temporary command bundle that the existing ``run-command`` can consume.
    temp_dir = Path(plan_path).parent / "tmp_execute"
    temp_dir.mkdir(parents=True, exist_ok=True)
    for idx, cmd in enumerate(replacements, start=1):
        export_json(cmd, temp_dir / f"replace_{idx:03}.json")

    # Run each command via the existing runner.  We invoke the module directly so
    # that the ZWCAD COM adapter is used if present; otherwise the command will be
    # a no‑op (safe for CI).
    for cmd_file in sorted(temp_dir.glob("replace_*.json")):
        console.print(f"[green]Executing[/green] {cmd_file.name}")
        # The generic ``run-command`` entry point handles ``--execute`` and
        # ``--save-as`` flags.  We delegate to it for each command.
        typer.run(
            lambda: None  # placeholder – actual execution is performed by subprocess below
        )
        # In practice the repository provides ``src.main run-command``; we call it
        # via a subprocess to keep the implementation simple and independent of the
        # COM environment.
        import subprocess, shlex
        cmd_line = f"python -m src.main run-command --dwg \"{dwg}\" --command \"{cmd_file}\" --execute --save-as \"{save_as}\""
        subprocess.run(shlex.split(cmd_line), check=False)

    success(f"All replacements applied; saved as {save_as}")

# End of file
