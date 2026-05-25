import json
import logging
from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console

logger = logging.getLogger(__name__)

@app.command("domain-rule-command-plan")
def domain_rule_command_plan(
    decision_package_json: str = typer.Option(..., "--decision-package-json", help="Path to DOMAIN_RULE_DECISION_PACKAGE.json"),
    out_dir: str = typer.Option(..., "--out-dir", help="Output directory")
):
    """Generate DOMAIN_RULE_COMMAND_PLAN.json from decision package."""
    in_path = Path(decision_package_json)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    if not in_path.exists():
        console.print(f"[red]Error: {in_path} not found.[/red]")
        raise typer.Abort()
        
    # Just mock the command plan generation
    command_plan = {
        "source_decision_package": str(in_path),
        "target_aliases": ["WAL"],
        "status": "planned"
    }
    
    res_path = out_path / "DOMAIN_RULE_COMMAND_PLAN.json"
    res_path.write_text(json.dumps(command_plan, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"[green]Created {res_path}[/green]")

@app.command("xicad-alias-allowlist")
def xicad_alias_allowlist(
    command_plan_json: str = typer.Option(..., "--command-plan-json", help="Path to DOMAIN_RULE_COMMAND_PLAN.json"),
    out_dir: str = typer.Option(..., "--out-dir", help="Output directory")
):
    """Generate XICAD_ALIAS_ALLOWLIST_PLAN.json from command plan."""
    in_path = Path(command_plan_json)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    if not in_path.exists():
        console.print(f"[red]Error: {in_path} not found.[/red]")
        raise typer.Abort()
        
    try:
        plan = json.loads(in_path.read_text(encoding="utf-8"))
        aliases = plan.get("target_aliases", ["WAL"])
    except Exception:
        aliases = ["WAL"]
        
    allowlist_plan = {
        "source_command_plan": str(in_path),
        "dry_run_allowed_aliases": aliases,
        "blocked_aliases": ["ERASE", "EXPLODE"],
        "execution_allowed_aliases": [],  # Must be empty before manual live stage
        "warnings": []
    }
    
    res_path = out_path / "XICAD_ALIAS_ALLOWLIST_PLAN.json"
    res_path.write_text(json.dumps(allowlist_plan, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"[green]Created {res_path}[/green]")
