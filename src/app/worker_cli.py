from __future__ import annotations

import json
from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console, success
from src.workers.contracts import WorkerInput
from src.workers.registry import WorkerRegistry
from src.workers.runner import WorkerRunner


@app.command('hscad-workers')
def hscad_workers(
    manifest: Path = typer.Option(Path('config/worker_manifest.json'), '--manifest'),
    out_json: Path | None = typer.Option(None, '--out-json'),
):
    registry = WorkerRegistry(manifest)
    summary = registry.summary()
    console.print(summary)
    if out_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    success('Worker manifest summary written')


@app.command('hscad-worker-run')
def hscad_worker_run(
    worker_name: str = typer.Argument(...),
    workspace: Path = typer.Option(..., '--workspace', '-w'),
    manifest: Path = typer.Option(Path('config/worker_manifest.json'), '--manifest'),
    dry_run: bool = typer.Option(False, '--dry-run'),
    snap_tolerance: float = typer.Option(0.0, '--snap-tolerance'),
):
    worker_input = WorkerInput(
        worker_name=worker_name,
        task='run',
        workspace=str(workspace),
        input_artifacts=[
            str(workspace / 'fileized' / 'json'),
            str(workspace / 'AREA_ELEMENTS.json'),
        ],
        options={'snap_tolerance': snap_tolerance},
    )
    runner = WorkerRunner(WorkerRegistry(manifest))
    if dry_run:
        console.print(runner.dry_run(worker_name, worker_input))
        return
    output = runner.run(worker_name, worker_input)
    console.print(output.to_dict())
    if output.status in {'ok', 'warning'}:
        success('Worker completed')
    elif output.status == 'unavailable':
        console.print('[yellow]Worker unavailable[/yellow]')
    else:
        raise typer.Exit(code=1)
