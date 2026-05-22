from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.table import Table

from src.app.cli import app
from src.app.logger import console, success
from src.orchestrator.task_router import TaskRouter


@app.command('hscad-route')
def hscad_route(
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
    if route.warnings:
        console.print({'warnings': route.warnings})
    if route.missing_context:
        console.print({'missing_context': route.missing_context})

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / 'task_route.json'
    md_path = out_dir / 'task_route.md'
    json_path.write_text(json.dumps(route.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')
    md_path.write_text(_to_markdown(route.to_dict()), encoding='utf-8')
    success(f'HS-CAD task route written: {json_path}, {md_path}')


def _to_markdown(payload: dict) -> str:
    lines = [
        '# HS-CAD Task Route',
        '',
        f'- Prompt: {payload.get("user_prompt")}',
        f'- Source: {payload.get("source_path") or "not provided"}',
        f'- Extension: {payload.get("source_extension") or "unknown"}',
        f'- Intent: {payload.get("intent")}',
        f'- Pipeline: {payload.get("pipeline")}',
        '',
        '## Tools',
        '| Stage | Tool | Command | Review | Reason |',
        '|---|---|---|---|---|',
    ]
    for tool in payload.get('tools', []):
        review = 'yes' if tool.get('review_required') else 'no'
        lines.append(f'| {tool.get("stage")} | {tool.get("name")} | `{tool.get("command")}` | {review} | {tool.get("reason")} |')
    if payload.get('warnings'):
        lines += ['', '## Warnings'] + [f'- {item}' for item in payload['warnings']]
    if payload.get('missing_context'):
        lines += ['', '## Missing Context'] + [f'- {item}' for item in payload['missing_context']]
    return '\n'.join(lines) + '\n'
