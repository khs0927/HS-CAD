from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from src.app.cli import app
from src.app.logger import console, success
from src.orchestrator.tool_registry import build_default_registry
from src.orchestrator.workflow_planner import plan_hscad_workflow, write_plan_files
from src.reports.json_exporter import export_json


@app.command('hscad-tools')
def hscad_tools(
    query: str = typer.Option('', '--query', '-q', help='Filter tools by keyword.'),
    family: str | None = typer.Option(None, '--family', help='Filter by tool family.'),
    out: Path | None = typer.Option(None, '--out', help='Optional JSON output path.'),
):
    """List every registered HS-CAD tool so no capability is missed."""
    registry = build_default_registry()
    tools = registry.find(query=query, family=family)
    table = Table('Priority', 'Family', 'Tool', 'Command', 'Safe', 'Needs Review')
    for tool in tools:
        needs_review = tool.requires_execute or tool.requires_save_as
        table.add_row(str(tool.priority), tool.family, tool.name, tool.command, str(tool.safe_default), str(needs_review))
    console.print(table)
    payload = {'query': query, 'family': family, 'tools': [tool.to_dict() for tool in tools], 'tool_count': len(tools)}
    if out:
        export_json(payload, out)
        success(f'HS-CAD tool registry written: {out}')


@app.command('hscad-workflow-plan')
def hscad_tool_plan(
    task: str = typer.Argument(..., help='Natural-language CAD task to plan.'),
    has_image: bool = typer.Option(False, '--has-image', help='The task includes an image/PDF floorplan input.'),
    has_dwg: bool = typer.Option(False, '--has-dwg', help='The task includes an existing DWG or active drawing.'),
    wants_write: bool = typer.Option(False, '--wants-write', help='The user intends to change a drawing. This makes the plan review-gated.'),
    out_dir: Path = typer.Option(Path('outputs/tool_plan'), '--out-dir', help='Directory for workflow plan JSON/Markdown.'),
):
    """Create a priority-ordered HS-CAD workflow before running tools.

    This command is planning-only. It does not open, modify, save, delete, purge,
    or explode any drawing. Use the returned plan to decide the safest next
    command sequence.
    """
    plan = plan_hscad_workflow(task, has_image=has_image, has_dwg=has_dwg, wants_write=wants_write)
    paths = write_plan_files(plan, out_dir)

    table = Table('#', 'Tool', 'Command', 'Review')
    for step in plan.steps:
        table.add_row(str(step.order), step.tool, step.command, 'yes' if step.needs_review else 'no')
    console.print(table)
    if plan.warnings:
        console.print({'warnings': plan.warnings})
    if plan.held_steps:
        console.print({'review_gated_steps': plan.held_steps})
    if plan.missing_context:
        console.print({'missing_context': plan.missing_context})
    success(f'HS-CAD workflow plan written: {paths}')
