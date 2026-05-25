from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from src.app.cli import app
from src.app.logger import console, success, warn
from src.orchestrator.xicad_contract_test_plan import create_contract_test_plan
from src.orchestrator.xicad_contracts import XiCADContractEvidence, write_evidence, read_evidence
from src.orchestrator.xicad_contract_validator import (
    validate_contract_evidence,
    write_validation_result,
    write_promotion_candidate,
)
from src.orchestrator.xicad_contract_report import load_and_summarize_contracts


@app.command("xicad-contract-plan")
def xicad_contract_plan(
    aliases: str = typer.Option("WAL,D1,W1,INS,COL,BE,AE,LC", "--aliases", help="Comma-separated XiCAD aliases to verify."),
    out_dir: Path = typer.Option(Path("outputs/xicad_contracts"), "--out-dir", help="Output directory."),
):
    """Create a manual XiCAD command contract verification plan."""
    paths = create_contract_test_plan(aliases, out_dir)
    console.print(paths)
    success("XiCAD contract verification plan written.")


@app.command("xicad-contract-summary")
def xicad_contract_summary(
    contracts: Path = typer.Option(..., "--contracts", help="xicad_contract_plan.json path."),
):
    """Summarize a XiCAD contract plan."""
    summary = load_and_summarize_contracts(contracts)
    console.print(summary)


@app.command("xicad-contract-record")
def xicad_contract_record(
    alias: str = typer.Option(..., "--alias", help="XiCAD alias."),
    status: str = typer.Option("failed", "--status", help="passed or failed."),
    manual_zwcad_version: str = typer.Option("", "--zwcad-version", help="Observed ZWCAD version."),
    xicad_version: str = typer.Option("", "--xicad-version", help="Observed XiCAD version."),
    xicad_root: str = typer.Option("", "--xicad-root", help="XiCAD root path used during manual test."),
    prompt_sequence: str = typer.Option("", "--prompts", help="Prompt sequence separated by |."),
    argument_pattern: str = typer.Option("", "--args-pattern", help="Accepted argument pattern separated by |."),
    output_observation: str = typer.Option("", "--output-observation", help="Observed output."),
    rollback_observation: str = typer.Option("", "--rollback-observation", help="Rollback/undo observation."),
    safety_observation: str = typer.Option("", "--safety-observation", help="Safety observation."),
    no_save_confirmed: bool = typer.Option(False, "--no-save-confirmed", help="Confirm no save happened."),
    no_delete_confirmed: bool = typer.Option(False, "--no-delete-confirmed", help="Confirm no delete happened."),
    no_explode_confirmed: bool = typer.Option(False, "--no-explode-confirmed", help="Confirm no explode happened."),
    notes: str = typer.Option("", "--notes", help="Manual notes."),
    out: Path = typer.Option(Path("outputs/xicad_contracts/contract_record.json"), "--out", help="Output evidence JSON."),
):
    """Record manual ZWCAD+XiCAD contract test evidence.

    This command does not run XiCAD. It only writes the human-observed result.
    """
    evidence = XiCADContractEvidence(
        alias=alias.upper(),
        status=status,
        manual_zwcad_version=manual_zwcad_version,
        xicad_version=xicad_version,
        xicad_root=xicad_root,
        observed_prompt_sequence=tuple(part.strip() for part in prompt_sequence.split("|") if part.strip()),
        accepted_argument_pattern=tuple(part.strip() for part in argument_pattern.split("|") if part.strip()),
        output_observation=output_observation,
        rollback_observation=rollback_observation,
        safety_observation=safety_observation,
        no_save_confirmed=no_save_confirmed,
        no_delete_confirmed=no_delete_confirmed,
        no_explode_confirmed=no_explode_confirmed,
        notes=notes,
    )
    path = write_evidence(evidence, out)
    success(f"XiCAD contract evidence written: {path}")


@app.command("xicad-contract-validate")
def xicad_contract_validate(
    record: Path = typer.Option(..., "--record", help="Contract evidence JSON path."),
    out: Path | None = typer.Option(None, "--out", help="Optional validation result JSON path."),
):
    """Validate whether a manual contract evidence record is sufficient for promotion."""
    evidence = read_evidence(record)
    result = validate_contract_evidence(evidence, evidence_path=record)

    table = Table("Alias", "Status", "CanPromote", "Missing")
    table.add_row(result.alias, result.status, str(result.can_promote), ", ".join(result.missing))
    console.print(table)

    if out:
        write_validation_result(result, out)
        success(f"Validation result written: {out}")


@app.command("xicad-contract-promotion-candidate")
def xicad_contract_promotion_candidate(
    record: Path = typer.Option(..., "--record", help="Contract evidence JSON path."),
    out: Path = typer.Option(Path("outputs/xicad_contracts/promotion_candidate.json"), "--out", help="Output candidate JSON."),
):
    """Write a promotion candidate if evidence is sufficient.

    This does not edit xicad_recipe_registry.py.
    """
    evidence = read_evidence(record)
    result = validate_contract_evidence(evidence, evidence_path=record)
    if not result.can_promote:
        warn({"status": "BLOCKED", "missing": result.missing})
        raise typer.Exit(code=1)
    write_promotion_candidate(result, out)
    success(f"Promotion candidate written for human review: {out}")
