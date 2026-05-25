from __future__ import annotations

import json
import time
import webbrowser
from pathlib import Path
from typing import Iterable

import typer
from rich.table import Table

from src.app.cli import app
from src.app.logger import console, success, warn
from src.workers.contracts import WorkerInput
from src.workers.registry import WorkerRegistry
from src.workers.runner import WorkerRunner

DEFAULT_ANALYSIS_WORKERS = [
    "analysis_core_megapack",
    "analysis_graph_megapack",
    "analysis_advanced_megapack",
    "analysis_ops_megapack",
    "analysis_automation_megapack",
    "analysis_evidence_megapack",
]


def _worker_input(worker_name: str, workspace: Path, *, snap_tolerance: float = 0.0, options: dict | None = None) -> WorkerInput:
    merged_options = {"snap_tolerance": snap_tolerance}
    if options:
        merged_options.update(options)
    return WorkerInput(
        worker_name=worker_name,
        task="run",
        workspace=str(workspace),
        input_artifacts=[
            str(workspace / "fileized" / "json"),
            str(workspace / "AREA_ELEMENTS.json"),
            str(workspace / "TEXT_ROLE_INFERENCE.json"),
            str(workspace / "REAL_GEOMETRY_POLYGONIZER.json"),
            str(workspace / "STRTREE_SPATIAL_JOIN.json"),
        ],
        options=merged_options,
    )


def _write_summary(workspace: Path, payload: dict) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "ANALYSIS_RUN_ALL_SUMMARY.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# HS-CAD Analysis Run All Summary",
        "",
        f"- Workspace: `{payload.get('workspace')}`",
        f"- Worker count: `{payload.get('summary', {}).get('worker_count')}`",
        f"- OK count: `{payload.get('summary', {}).get('ok_count')}`",
        f"- Warning count: `{payload.get('summary', {}).get('warning_count')}`",
        f"- Error count: `{payload.get('summary', {}).get('error_count')}`",
        "",
        "| Order | Worker | Status | Duration sec | Artifacts |",
        "|---:|---|---|---:|---:|",
    ]
    for row in payload.get("results", []):
        lines.append(f"| {row.get('order')} | {row.get('worker_name')} | {row.get('status')} | {row.get('duration_sec')} | {row.get('artifact_count')} |")
    (workspace / "ANALYSIS_RUN_ALL_SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_worker_sequence(
    workers: Iterable[str],
    *,
    workspace: Path,
    manifest: Path,
    dry_run: bool,
    stop_on_error: bool,
    snap_tolerance: float,
    automation_dry_run: bool,
) -> dict:
    registry = WorkerRegistry(manifest)
    runner = WorkerRunner(registry)
    results = []
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for order, worker_name in enumerate(workers, start=1):
        t0 = time.time()
        row = {"order": order, "worker_name": worker_name, "status": "planned", "duration_sec": 0.0, "artifact_count": 0, "warnings": [], "error": None}
        try:
            options = {"dry_run": automation_dry_run} if worker_name == "analysis_automation_megapack" else {}
            worker_input = _worker_input(worker_name, workspace, snap_tolerance=snap_tolerance, options=options)
            if dry_run:
                row["status"] = "dry_run"
                row["dry_run"] = runner.dry_run(worker_name, worker_input)
            else:
                output = runner.run(worker_name, worker_input)
                row["status"] = output.status
                row["artifact_count"] = len(output.artifacts or [])
                row["artifacts"] = output.artifacts
                row["warnings"] = output.warnings or []
                row["metrics"] = output.metrics or {}
                if output.status not in {"ok", "warning", "unavailable"}:
                    row["error"] = "worker returned non-success status"
        except Exception as exc:
            row["status"] = "error"
            row["error"] = str(exc)
        row["duration_sec"] = round(time.time() - t0, 6)
        results.append(row)
        if row["status"] == "error" and stop_on_error:
            break
    payload = {
        "backend": "analysis_shortcut_cli",
        "schema_version": "0.1",
        "started_at": started,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "workspace": str(workspace),
        "manifest": str(manifest),
        "summary": {
            "worker_count": len(results),
            "ok_count": sum(1 for r in results if r["status"] == "ok"),
            "warning_count": sum(1 for r in results if r["status"] == "warning"),
            "unavailable_count": sum(1 for r in results if r["status"] == "unavailable"),
            "dry_run_count": sum(1 for r in results if r["status"] == "dry_run"),
            "error_count": sum(1 for r in results if r["status"] == "error"),
        },
        "results": results,
        "warnings": ["Validation remains TODO-only until local webhard batch testing is performed.", "No source drawing mutation is performed."],
    }
    _write_summary(workspace, payload)
    return payload


@app.command("hscad-analysis-run-all")
def hscad_analysis_run_all(
    workspace: Path = typer.Option(..., "--workspace", "-w"),
    manifest: Path = typer.Option(Path("config/worker_manifest.json"), "--manifest"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    stop_on_error: bool = typer.Option(True, "--stop-on-error/--continue-on-error"),
    snap_tolerance: float = typer.Option(0.0, "--snap-tolerance"),
    automation_dry_run: bool = typer.Option(True, "--automation-dry-run/--automation-execute"),
):
    """Run all analysis megapack workers in recommended order."""
    payload = _run_worker_sequence(DEFAULT_ANALYSIS_WORKERS, workspace=workspace, manifest=manifest, dry_run=dry_run, stop_on_error=stop_on_error, snap_tolerance=snap_tolerance, automation_dry_run=automation_dry_run)
    table = Table("Order", "Worker", "Status", "Duration", "Artifacts")
    for row in payload["results"]:
        table.add_row(str(row["order"]), row["worker_name"], row["status"], str(row["duration_sec"]), str(row.get("artifact_count", 0)))
    console.print(table)
    success(f"Analysis run summary written: {workspace / 'ANALYSIS_RUN_ALL_SUMMARY.md'}")
    if payload["summary"]["error_count"] > 0:
        raise typer.Exit(code=1)


@app.command("hscad-analysis-summary")
def hscad_analysis_summary(
    workspace: Path = typer.Option(..., "--workspace", "-w"),
    manifest: Path = typer.Option(Path("config/worker_manifest.json"), "--manifest"),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    """Regenerate summary/evidence/report artifacts only."""
    payload = _run_worker_sequence(["analysis_ops_megapack", "analysis_automation_megapack", "analysis_evidence_megapack"], workspace=workspace, manifest=manifest, dry_run=dry_run, stop_on_error=True, snap_tolerance=0.0, automation_dry_run=True)
    console.print(payload["summary"])
    success(f"Analysis summary artifacts refreshed in: {workspace}")


@app.command("hscad-analysis-dashboard")
def hscad_analysis_dashboard(
    workspace: Path = typer.Option(..., "--workspace", "-w"),
    manifest: Path = typer.Option(Path("config/worker_manifest.json"), "--manifest"),
    regenerate: bool = typer.Option(True, "--regenerate/--no-regenerate"),
    open_browser: bool = typer.Option(False, "--open"),
):
    """Generate and print the validation dashboard path."""
    if regenerate:
        _run_worker_sequence(["analysis_ops_megapack", "analysis_automation_megapack", "analysis_evidence_megapack"], workspace=workspace, manifest=manifest, dry_run=False, stop_on_error=False, snap_tolerance=0.0, automation_dry_run=True)
    dashboard = workspace / "VALIDATION_DASHBOARD.html"
    console.print({"dashboard": str(dashboard), "exists": dashboard.exists()})
    if open_browser and dashboard.exists():
        webbrowser.open(dashboard.resolve().as_uri())
    if dashboard.exists():
        success(f"Dashboard ready: {dashboard}")
    else:
        warn(f"Dashboard not found: {dashboard}")


@app.command("hscad-analysis-package")
def hscad_analysis_package(
    workspace: Path = typer.Option(..., "--workspace", "-w"),
    output: Path | None = typer.Option(None, "--output", "-o"),
    create_zip: bool = typer.Option(False, "--create-zip"),
):
    """Preview or create a zip from REPORT_PACKAGE_MANIFEST.json."""
    manifest_path = workspace / "REPORT_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    files = manifest.get("files") or []
    if not create_zip:
        console.print({"manifest": str(manifest_path), "file_count": len(files), "create_zip": False})
        return
    import zipfile
    zip_path = output or (workspace / f"{workspace.name}_hscad_validation_report.zip")
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in files:
            rel = Path(str(row.get("path") or ""))
            src = workspace / rel
            if src.exists() and src.is_file():
                zf.write(src, rel.as_posix())
    success(f"Report zip written: {zip_path}")
