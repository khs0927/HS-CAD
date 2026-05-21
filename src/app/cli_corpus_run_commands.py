"""CLI sub‑app for the operational ``corpus‑run`` pipeline.

Provides commands to prepare a workspace, run the full pipeline, continue a
partial run, query the corpus, generate the final report, inspect failures, and
retry failed file‑level operations.
"""

from __future__ import annotations

from pathlib import Path
import json

import typer

from src.corpus_run.pipeline_runner import (
    run_prepare,
    run_execute,
    run_continue,
    execute_query,
    generate_report,
    run_failures,
    run_retry_failures,
)

corpus_run_app = typer.Typer(help="Operational corpus‑run pipeline commands.")


@corpus_run_app.command("prepare")
def prepare_command(
    root: str = typer.Option(..., "--root", help="Root folder containing drawing files"),
    workspace: str = typer.Option(..., "--workspace", help="Directory where the run artefacts will be stored"),
    sample: int = typer.Option(0, "--sample", help="Number of files to mark as pending initially (0 = all)"),
) -> None:
    """Create a fresh workspace and manifest for a new run."""
    run_prepare(root, workspace, sample=sample)
    typer.echo(f"Workspace prepared at {workspace}")


@corpus_run_app.command("execute")
def execute_command(
    workspace: str = typer.Option(..., "--workspace", help="Workspace to run the pipeline in"),
    limit: int = typer.Option(None, "--limit", help="Optional limit on number of files to index"),
    force: bool = typer.Option(False, "--force", help="Force re‑indexing of all fileized records"),
) -> None:
    """Run the full pipeline: fileize → index → learn."""
    result = run_execute(workspace, limit=limit, force=force)
    typer.echo("Pipeline execution completed.")
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@corpus_run_app.command("continue")
def continue_command(
    workspace: str = typer.Option(..., "--workspace", help="Workspace to continue the pipeline in"),
    limit: int = typer.Option(None, "--limit", help="Optional limit on number of files to index"),
    force: bool = typer.Option(False, "--force", help="Force re‑indexing of all fileized records"),
) -> None:
    """Continue a previously interrupted run (re‑executes execute)."""
    result = run_continue(workspace, limit=limit, force=force)
    typer.echo("Continuation completed.")
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@corpus_run_app.command("query")
def query_command(
    workspace: str = typer.Option(..., "--workspace", help="Workspace containing the indexed corpus"),
    query: str = typer.Option(..., "--query", help="Natural language query string"),
    limit: int = typer.Option(30, "--limit", help="Maximum number of evidence hits"),
) -> None:
    """Run a query and create an evidence pack."""
    result = execute_query(workspace, query=query, limit=limit)
    typer.echo("Query completed.")
    # The evidence pack is a dataclass; convert to dict for JSON output
    pack = result.get("evidence_pack")
    if pack:
        typer.echo(json.dumps(pack.__dict__, ensure_ascii=False, indent=2))
    else:
        typer.echo("No evidence pack generated.")


@corpus_run_app.command("report")
def report_command(
    workspace: str = typer.Option(..., "--workspace", help="Workspace to generate the final report from"),
    company_profile: str = typer.Option(None, "--company-profile", help="Optional path to a company drafting profile JSON"),
) -> None:
    """Generate the final markdown report (FINAL_REPORT.md)."""
    result = generate_report(workspace, company_profile_path=company_profile)
    typer.echo(f"Report written to {result.get('report_path')}")


@corpus_run_app.command("failures")
def failures_command(
    workspace: str = typer.Option(..., "--workspace", help="Workspace to inspect failures for"),
) -> None:
    """Show a summary of file‑level failures recorded during fileization."""
    summary = run_failures(workspace)
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))


@corpus_run_app.command("retry-failures")
def retry_failures_command(
    workspace: str = typer.Option(..., "--workspace", help="Workspace to retry failures in"),
    limit: int = typer.Option(None, "--limit", help="Optional cap on number of retries"),
) -> None:
    """Retry failed file‑level operations up to *limit* items."""
    result = run_retry_failures(workspace, limit=limit)
    typer.echo("Retry completed.")
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
