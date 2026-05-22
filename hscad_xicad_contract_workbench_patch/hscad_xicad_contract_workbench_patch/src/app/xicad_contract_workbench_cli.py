from __future__ import annotations

from pathlib import Path
import typer

from src.app.cli import app
from src.app.logger import console, success
from src.orchestrator.xicad_contract_workbench import write_contract_session, write_review_matrix
from src.orchestrator.xicad_contract_bundle import validate_contract_bundle
from src.orchestrator.xicad_promotion_review import build_promotion_review_pack


@app.command("xicad-contract-session")
def xicad_contract_session(
    alias: str = typer.Option(..., "--alias", help="XiCAD alias to verify, e.g. WAL."),
    out_dir: Path = typer.Option(Path("outputs/xicad_sessions"), "--out-dir", help="Output directory."),
):
    """Create a manual contract verification session template for one alias."""
    paths = write_contract_session(alias, out_dir)
    console.print(paths)
    success("XiCAD contract session template written.")


@app.command("xicad-contract-review-matrix")
def xicad_contract_review_matrix(
    aliases: str = typer.Option("WAL,D1,W1,INS,COL,BE,AE,LC", "--aliases", help="Comma-separated aliases."),
    out_dir: Path = typer.Option(Path("outputs/xicad_sessions"), "--out-dir", help="Output directory."),
):
    """Create a review matrix for multiple XiCAD aliases."""
    paths = write_review_matrix(aliases, out_dir)
    console.print(paths)
    success("XiCAD contract review matrix written.")


@app.command("xicad-contract-bundle-validate")
def xicad_contract_bundle_validate(
    records_dir: Path = typer.Option(Path("outputs/xicad_contracts"), "--records-dir", help="Directory containing *_record.json files."),
    out_dir: Path = typer.Option(Path("outputs/xicad_contracts/bundle"), "--out-dir", help="Output directory."),
):
    """Validate all contract record files in a directory."""
    paths = validate_contract_bundle(records_dir, out_dir)
    console.print(paths)
    success("XiCAD contract bundle validation written.")


@app.command("xicad-contract-review-pack")
def xicad_contract_review_pack(
    records_dir: Path = typer.Option(Path("outputs/xicad_contracts"), "--records-dir", help="Directory containing *_record.json files."),
    out_dir: Path = typer.Option(Path("outputs/xicad_contracts/review_pack"), "--out-dir", help="Output directory."),
):
    """Build a human review pack from promotable contract records.

    This command does not modify xicad_recipe_registry.py.
    """
    paths = build_promotion_review_pack(records_dir, out_dir)
    console.print(paths)
    success("XiCAD promotion review pack written.")
