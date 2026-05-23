from __future__ import annotations

from src.domain_rules.decision_models import ModificationDecisionPackage


def render_decision_markdown(package: ModificationDecisionPackage) -> str:
    lines: list[str] = [
        '# HS-CAD Modification Decision Package',
        '',
        f'- Task: {package.task}',
        f'- Source: {package.source}',
        f'- Status: {package.status}',
        f'- Decision count: {len(package.decisions)}',
        '',
    ]
    if package.blocked_reasons:
        lines += ['## Blocked reasons']
        for item in package.blocked_reasons:
            lines.append(f'- {item}')
        lines.append('')
    if package.required_evidence:
        lines += ['## Required evidence']
        for item in package.required_evidence:
            lines.append(f'- {item}')
        lines.append('')
    lines += ['## Decisions']
    if not package.decisions:
        lines.append('- None')
    for item in package.decisions:
        lines.append(f'- **{item.decision_id}** — {item.title}')
        lines.append(f'  - Status: {item.status}')
        lines.append(f'  - Priority: {item.priority}')
        lines.append(f'  - Reason: {item.reason}')
        if item.rule_sources:
            lines.append(f'  - Rule sources: {", ".join(item.rule_sources)}')
        if item.command_hints:
            lines.append('  - Command hints:')
            for hint in item.command_hints:
                lines.append(f'    - `{hint}`')
        if item.next_steps:
            lines.append('  - Next steps:')
            for step in item.next_steps:
                lines.append(f'    - {step}')
    lines += ['', '## Review checklist']
    for item in package.review_checklist:
        lines.append(f'- {item}')
    if package.warnings:
        lines += ['', '## Warnings']
        for item in package.warnings:
            lines.append(f'- {item}')
    lines += ['', '## System drafting constraints', '', '```text', package.system_prompt.rstrip(), '```']
    return '\n'.join(lines).rstrip() + '\n'
