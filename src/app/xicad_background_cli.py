from __future__ import annotations

import json
import os
from pathlib import Path

import typer
from rich.table import Table

from src.app.cli import app
from src.app.logger import console, success, warn
from src.xicad_automation.catalog import AutomationCatalog
from src.xicad_automation.executor import BackgroundWorker, WorkflowExecutor
from src.xicad_automation.models import CommandStep, JobStatus, WorkflowSpec
from src.xicad_automation.store import JobStore
from src.xicad_automation.zwcad_gateway import MonitoredZWCADGateway

DEFAULT_DB = Path("outputs/xicad_background/jobs.sqlite3")


def _load_workflow(path: Path) -> WorkflowSpec:
    return WorkflowSpec.model_validate_json(path.read_text(encoding="utf-8"))


@app.command("xicad-bg-template")
def xicad_bg_template(
    source_dwg: Path = typer.Option(..., "--source-dwg"),
    working_dwg: Path = typer.Option(..., "--working-dwg"),
    xicad_root: Path = typer.Option(..., "--xicad-root"),
    out: Path = typer.Option(Path("outputs/xicad_background/workflow.json"), "--out"),
):
    """Create a dry-run architectural workflow template."""
    workflow = WorkflowSpec(
        name="Architectural floor-plan automation",
        source_dwg=source_dwg,
        working_dwg=working_dwg,
        xicad_root=xicad_root,
        dry_run=True,
        steps=[
            CommandStep(alias="WAL", allow_interactive=True, arguments=[], description="Wall drawing contract"),
            CommandStep(alias="D1", allow_interactive=True, arguments=[], description="Door placement contract"),
            CommandStep(alias="W1", allow_interactive=True, arguments=[], description="Window placement contract"),
            CommandStep(alias="INS", allow_interactive=True, arguments=[], description="Insulation contract"),
            CommandStep(alias="AE", allow_interactive=True, arguments=[], description="Area annotation contract"),
        ],
        metadata={
            "instructions": "Fill each step.arguments with the exact prompt answers observed through xicad-contract-wizard. Keep dry_run=true until validation passes."
        },
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(workflow.model_dump_json(indent=2), encoding="utf-8")
    success(f"Workflow template written: {out}")


@app.command("xicad-bg-catalog")
def xicad_bg_catalog(
    xicad_root: Path = typer.Option(..., "--xicad-root"),
    out: Path | None = typer.Option(None, "--out"),
):
    """List every discovered XiCAD alias and its unattended readiness."""
    rows = AutomationCatalog.from_xicad_root(xicad_root).describe()
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        success(f"XiCAD catalog written: {out}")
        return
    table = Table("Alias", "Name", "Category", "Risk", "Interactive", "Unattended")
    for row in rows:
        table.add_row(
            row["alias"],
            row["name"],
            row["category"],
            row["risk"],
            str(row["interactive_required"]),
            str(row["unattended_ready"]),
        )
    console.print(table)


@app.command("xicad-bg-token")
def xicad_bg_token(workflow: Path = typer.Option(..., "--workflow")):
    """Print the approval token for this exact non-dry-run workflow."""
    spec = _load_workflow(workflow)
    console.print(spec.expected_approval_token())


@app.command("xicad-bg-submit")
def xicad_bg_submit(
    workflow: Path = typer.Option(..., "--workflow"),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
):
    """Submit a workflow to the persistent queue."""
    spec = _load_workflow(workflow)
    job = JobStore(db).enqueue(spec)
    success(f"Queued XiCAD job: {job.id} ({job.status.value})")


@app.command("xicad-bg-status")
def xicad_bg_status(
    job_id: str | None = typer.Option(None, "--job-id"),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    limit: int = typer.Option(20, "--limit"),
):
    """Show one job or the recent queue."""
    store = JobStore(db)
    jobs = [store.get(job_id)] if job_id else store.list(limit=limit)
    table = Table("Job", "Status", "Workflow", "Attempts", "Updated", "Error")
    for job in jobs:
        table.add_row(job.id, job.status.value, job.workflow.name, str(job.attempts), job.updated_at, job.error or "")
    console.print(table)


@app.command("xicad-bg-cancel")
def xicad_bg_cancel(
    job_id: str = typer.Option(..., "--job-id"),
    db: Path = typer.Option(DEFAULT_DB, "--db"),
):
    job = JobStore(db).cancel(job_id)
    success(f"Job {job.id}: {job.status.value}")


@app.command("xicad-bg-worker")
def xicad_bg_worker(
    db: Path = typer.Option(DEFAULT_DB, "--db"),
    once: bool = typer.Option(False, "--once"),
    visible: bool = typer.Option(True, "--visible/--hidden"),
    zwcad_version: str | None = typer.Option(None, "--zwcad-version"),
    poll_seconds: float = typer.Option(2.0, "--poll-seconds"),
):
    """Run the persistent XiCAD COM worker. Use Windows Task Scheduler for startup."""
    if os.name != "nt" and not once:
        raise typer.BadParameter("Continuous live XiCAD execution requires Windows")
    store = JobStore(db)
    executor = WorkflowExecutor(
        lambda: MonitoredZWCADGateway(visible=visible, version=zwcad_version)
    )
    worker = BackgroundWorker(store, executor)
    if once:
        processed = worker.run_once()
        console.print({"processed": processed, "worker_id": worker.worker_id})
        return
    warn(f"XiCAD background worker started: {worker.worker_id}")
    worker.run_forever(poll_seconds=poll_seconds)
