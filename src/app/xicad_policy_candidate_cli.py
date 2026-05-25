from __future__ import annotations

import typer

from src.app.cli import app
from src.app.logger import console
from src.execution.xicad_safe_runner import XiCADSafeRunner
from src.workers.xicad_policy_candidate_worker import run_xicad_policy_candidate_worker


@app.command("xicad-policy-candidates")
def xicad_policy_candidates(
    xicad_root: str = typer.Option("C:/xicad", help="XiCAD root path"),
    out_dir: str = typer.Option("outputs/xicad_policy_candidates", help="Output directory"),
    policy_override_path: str | None = typer.Option(None, help="Optional alias policy override JSON"),
):
    result = run_xicad_policy_candidate_worker(
        xicad_root=xicad_root,
        out_dir=out_dir,
        policy_override_path=policy_override_path,
    )
    console.print(result)


@app.command("xicad-safe-runner-dry-run")
def xicad_safe_runner_dry_run(
    alias_or_hint: str = typer.Argument(..., help="XiCAD alias or command hint"),
    policy_override_path: str | None = typer.Option(None, help="Optional alias policy override JSON"),
):
    runner = XiCADSafeRunner(policy_override_path=policy_override_path)
    result = runner.dry_run_alias(alias_or_hint)
    console.print(result)
