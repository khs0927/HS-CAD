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
    workspace: Path = typer.Option(Path('outputs/routed_corpus'), '--workspace'),
    out_dir: Path = typer.Option(Path('outputs/task_route'), '--out-dir'),
):
    route = TaskRouter().route(prompt, source, workspace=workspace)
    table = Table('Stage', 'Tool', 'Command', 'Review')
    for tool in route.tools:
        table.add_row(tool.stage, tool.name, tool.command, 'yes' if tool.review_required else 'no')
    console.print(table)
    paths = RoutePlanWriter(out_dir).write(route)
    success(f'HS-CAD routed review artifacts written: {paths}')
