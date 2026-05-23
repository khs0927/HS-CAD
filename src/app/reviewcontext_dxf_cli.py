from __future__ import annotations

from pathlib import Path

import typer

from src.app.cli import app
from src.integration.reviewcontext_dxf_merge import command_plan_from_review, review_dxf_file, review_fileized_record

reviewcontext_dxf_app = typer.Typer(help="No-COM DXF/fileized ReviewContext QA bridge")
app.add_typer(reviewcontext_dxf_app, name="hscad-qa")


@reviewcontext_dxf_app.command("review-fileized")
def review_fileized(
    input: Path = typer.Option(..., "--input", "-i", help="HS-CAD fileized JSON record"),
    out: Path = typer.Option(Path("outputs/qa/review_report.json"), "--out", "-o"),
):
    """Run spatial domain QA on an already fileized DXF/DWG-converted record."""
    payload = review_fileized_record(input, out)
    typer.echo(f"review written: {out} violations={payload['summary']['violation_count']}")


@reviewcontext_dxf_app.command("review-dxf")
def review_dxf(
    dxf: Path = typer.Option(..., "--dxf", help="DXF path parsed by ezdxf without ZWCAD COM"),
    out: Path = typer.Option(Path("outputs/qa/review_report.json"), "--out", "-o"),
    file_id: str | None = typer.Option(None, "--file-id"),
):
    """Parse DXF with ezdxf and run ReviewContext QA without opening CAD."""
    payload = review_dxf_file(dxf, out, file_id=file_id)
    typer.echo(f"DXF review written: {out} violations={payload['summary']['violation_count']}")


@reviewcontext_dxf_app.command("resolve")
def resolve(
    review: Path = typer.Option(..., "--review", help="Review report JSON"),
    out: Path = typer.Option(Path("outputs/qa/command_plan_report.json"), "--out", "-o"),
    engine: str = typer.Option("zwcad", "--engine"),
):
    """Convert approved-safe action candidates to dry-run command plans."""
    payload = command_plan_from_review(review, out, engine=engine)
    typer.echo(f"command plan written: {out} plans={payload['summary']['plan_count']}")
