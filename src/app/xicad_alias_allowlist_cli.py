from __future__ import annotations

import typer

from src.app.cli import app
from src.app.logger import console
from src.workers.xicad_alias_allowlist_worker import run_xicad_alias_allowlist_worker


@app.command("xicad-alias-allowlist")
def xicad_alias_allowlist(
    command_plan_json: str = typer.Option(..., help="DOMAIN_RULE_COMMAND_PLAN.json path"),
    out_dir: str = typer.Option("outputs/xicad_alias_allowlist", help="Output directory"),
):
    result = run_xicad_alias_allowlist_worker(command_plan_json, out_dir=out_dir)
    console.print(result)
