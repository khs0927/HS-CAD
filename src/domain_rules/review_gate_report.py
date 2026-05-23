from __future__ import annotations

from src.domain_rules.review_gate_models import ReviewGatePackage


def render_review_gate_markdown(package: ReviewGatePackage) -> str:
    lines: list[str] = [
        '# HS-CAD Domain Rule Review Gate',
        '',
        f'- Task: {package.task}',
        f'- Source command plan: {package.source_command_plan}',
        f'- Status: {package.status}',
        '',
        '## Gate checks',
    ]
    for check in package.checks:
        lines.append(f'- **{check.check_id}** [{check.status}] {check.title}')
        lines.append(f'  - {check.message}')
    if package.blocked_reasons:
        lines += ['', '## Blocked reasons']
        for reason in package.blocked_reasons:
            lines.append(f'- {reason}')
    lines += ['', '## Required sign-off']
    for item in package.signoff_required:
        lines.append(f'- [ ] {item}')
    lines += ['', '## Allowed next steps']
    for item in package.allowed_next_steps:
        lines.append(f'- {item}')
    if package.warnings:
        lines += ['', '## Warnings']
        for warning in package.warnings:
            lines.append(f'- {warning}')
    lines += [
        '',
        '## Safety note',
        '- This gate package does not execute CAD commands.',
        '- It only classifies whether a command plan can proceed to dry-run review.',
        '- Original DWG files must not be modified.',
    ]
    return '\n'.join(lines).rstrip() + '\n'
