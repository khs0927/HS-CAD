from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.entity_loader import write_json_and_md

SHORTCUTS = [
    {
        'name': 'hscad-analysis-run-all',
        'description': 'Run analysis_core, graph, advanced, ops, automation, and evidence megapacks in order.',
        'command_plan': [
            'analysis_core_megapack',
            'analysis_graph_megapack',
            'analysis_advanced_megapack',
            'analysis_ops_megapack',
            'analysis_automation_megapack',
            'analysis_evidence_megapack',
        ],
    },
    {
        'name': 'hscad-analysis-dashboard',
        'description': 'Open or generate validation dashboard artifacts.',
        'command_plan': ['analysis_ops_megapack', 'analysis_automation_megapack'],
    },
    {
        'name': 'hscad-analysis-summary',
        'description': 'Generate validation summary, evidence graph, validation rules, and package manifest.',
        'command_plan': ['analysis_ops_megapack', 'analysis_evidence_megapack'],
    },
]


def build_cli_shortcut_plan(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    rows = []
    for shortcut in SHORTCUTS:
        rows.append({
            **shortcut,
            'example': f"python -X utf8 -m src.main {shortcut['name']} --workspace {base}",
            'status': 'planned_not_registered',
        })
    payload = {
        'backend': 'cli_shortcut_plan',
        'schema_version': '0.1',
        'summary': {
            'shortcut_count': len(rows),
        },
        'shortcuts': rows,
        'todo': [
            'Add Typer/Click command registrations in src.main or src.app.cli.',
            'Implement hscad-analysis-run-all with safe ordered worker execution.',
            'Implement hscad-analysis-dashboard to print/open VALIDATION_DASHBOARD.html path.',
            'Implement hscad-analysis-summary to regenerate summary/evidence/report artifacts.',
            'Add tests for shortcut command help text and dry-run behavior.',
        ],
        'warnings': ['shortcut plan only; CLI commands are not registered yet'],
    }
    return write_json_and_md(base, 'CLI_SHORTCUT_PLAN', payload, _markdown(payload))


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        '# CLI Shortcut Plan',
        '',
        '| Shortcut | Status | Description |',
        '|---|---|---|',
    ]
    for row in payload.get('shortcuts') or []:
        lines.append(f"| {row.get('name')} | {row.get('status')} | {row.get('description')} |")
    lines.append('')
    lines.append('## TODO')
    lines.append('')
    for item in payload.get('todo') or []:
        lines.append(f'- {item}')
    lines.append('')
    return '\n'.join(lines)
