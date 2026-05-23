from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from src.app.cli import app
from src.app.logger import console, success
from src.orchestrator.route_plan_writer import RoutePlanWriter
from src.orchestrator.task_router import TaskRouter


@app.command('hscad-route-plan')
def hscad_route_plan(
    prompt: str = typer.Argument(...),
    source: Path | None = typer.Option(None, '--source', '-s'),
    workspace: Path | None = typer.Option(None, '--workspace'),
    sample: int | None = typer.Option(None, '--sample'),
    limit: int | None = typer.Option(None, '--limit'),
    out_dir: Path = typer.Option(Path('outputs/task_route'), '--out-dir'),
):
    route = TaskRouter().route(prompt, source, workspace=workspace, sample=sample, limit=limit)
    table = Table('Stage', 'Tool', 'Command', 'Review')
    for tool in route.tools:
        table.add_row(tool.stage, tool.name, tool.command, 'yes' if tool.review_required else 'no')
    console.print(table)
    if route.warnings:
        console.print({'warnings': route.warnings})
    if route.missing_context:
        console.print({'missing_context': route.missing_context})
    paths = RoutePlanWriter(out_dir).write(route)
    success(f'HS-CAD routed review artifacts written: {paths}')
