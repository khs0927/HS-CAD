from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.orchestrator.task_router import TaskRoute


class RoutePlanWriter:
    """Write a routed task as reviewable artifacts.

    This class intentionally writes commands only. It does not execute them.
    """

    def __init__(self, out_dir: str | Path):
        self.out_dir = Path(out_dir)

    def write(self, route: TaskRoute) -> dict[str, str]:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        payload = route.to_dict()
        json_path = self.out_dir / 'task_route.json'
        md_path = self.out_dir / 'task_route.md'
        ps1_path = self.out_dir / 'task_route_review.ps1'
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        md_path.write_text(self.to_markdown(payload), encoding='utf-8')
        ps1_path.write_text(self.to_powershell(payload), encoding='utf-8-sig')
        return {'json': str(json_path), 'markdown': str(md_path), 'powershell': str(ps1_path)}

    @staticmethod
    def to_markdown(payload: dict[str, Any]) -> str:
        lines = [
            '# HS-CAD Routed Command Plan',
            '',
            f'- Prompt: {payload.get("user_prompt")}',
            f'- Source: {payload.get("source_path") or "not provided"}',
            f'- Extension: {payload.get("source_extension") or "unknown"}',
            f'- Intent: {payload.get("intent")}',
            f'- Pipeline: {payload.get("pipeline")}',
            f'- Workspace: {payload.get("workspace") or "not set"}',
            f'- Sample: {payload.get("sample")}',
            f'- Limit: {payload.get("limit")}',
            '',
            '## Ordered Commands',
            '| # | Stage | Tool | Command | Review | Reason |',
            '|---:|---|---|---|---|---|',
        ]
        for index, tool in enumerate(payload.get('tools', []), start=1):
            review = 'yes' if tool.get('review_required') else 'no'
            lines.append(
                f'| {index} | {tool.get("stage")} | {tool.get("name")} | `{tool.get("command")}` | {review} | {tool.get("reason")} |'
            )
        if payload.get('warnings'):
            lines += ['', '## Warnings'] + [f'- {item}' for item in payload['warnings']]
        if payload.get('missing_context'):
            lines += ['', '## Missing Context'] + [f'- {item}' for item in payload['missing_context']]
        return '\n'.join(lines) + '\n'

    @staticmethod
    def to_powershell(payload: dict[str, Any]) -> str:
        lines = [
            '# HS-CAD routed command review script',
            '# Generated for review. Inspect before running any command.',
            '$ErrorActionPreference = "Stop"',
            'chcp 65001 | Out-Null',
            '$env:PYTHONIOENCODING = "utf-8"',
            '[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()',
            '',
            f'# Prompt: {payload.get("user_prompt")}',
            f'# Pipeline: {payload.get("pipeline")}',
            f'# Workspace: {payload.get("workspace")}',
            '',
        ]
        for index, tool in enumerate(payload.get('tools', []), start=1):
            command = str(tool.get('command') or '').strip()
            if not command:
                continue
            lines.append(f'Write-Host "[{index}] {tool.get("stage")} / {tool.get("name")}"')
            if tool.get('review_required'):
                lines.append(f'# REVIEW REQUIRED: {command}')
            elif command.startswith('corpus-run') or command.startswith('hscad-') or command.startswith('floorplan-'):
                lines.append(f'python -X utf8 -m src.main {command}')
            else:
                lines.append(f'# External or planned command: {command}')
            lines.append('')
        return '\n'.join(lines)
