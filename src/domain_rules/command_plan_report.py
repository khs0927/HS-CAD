from __future__ import annotations

from src.domain_rules.command_plan_models import DomainRuleCommandPlan


def render_command_plan_markdown(plan: DomainRuleCommandPlan) -> str:
    lines: list[str] = [
        '# HS-CAD Domain Rule Command Plan',
        '',
        f'- Task: {plan.task}',
        f'- Source decision package: {plan.source_decision_package}',
        f'- Status: {plan.status}',
        f'- Dry-run step count: {len(plan.dry_run_steps)}',
        f'- Execution queue candidate steps: {len(plan.execution_queue_candidate.steps)}',
        '',
        '## Safety posture',
        '- This plan does not execute CAD commands.',
        '- All mutation-like commands are dry-run/review-gated.',
        '- Original DWG must not be mutated.',
        '- Use SaveAs and explicit human approval before execution.',
        '',
    ]
    if plan.blocked_reasons:
        lines += ['## Blocked reasons']
        for reason in plan.blocked_reasons:
            lines.append(f'- {reason}')
        lines.append('')
    lines += ['## Dry-run steps']
    for step in plan.dry_run_steps:
        lines.append(f'- **{step.order}. {step.title}**')
        lines.append(f'  - Step ID: {step.step_id}')
        lines.append(f'  - Risk: {step.risk}')
        lines.append(f'  - Command type: {step.command_type}')
        if step.command_hint:
            lines.append(f'  - Command hint: `{step.command_hint}`')
        if step.reason:
            lines.append(f'  - Reason: {step.reason}')
        if step.blocked_reason:
            lines.append(f'  - Blocked: {step.blocked_reason}')
    lines += ['', '## Review table']
    for row in plan.review_table:
        lines.append(
            f'- #{row.get("order")}: {row.get("title")} | risk={row.get("risk")} | command={row.get("command_type")} | decision={row.get("source_decision_id")}'
        )
    lines += ['', '## Execution queue candidate']
    queue = plan.execution_queue_candidate
    lines.append(f'- Queue ID: {queue.queue_id}')
    lines.append(f'- Status: {queue.status}')
    lines.append(f'- Approval required: {queue.approval_required}')
    lines.append(f'- SaveAs required: {queue.save_as_required}')
    for note in queue.notes:
        lines.append(f'- Note: {note}')
    if plan.warnings:
        lines += ['', '## Warnings']
        for warning in plan.warnings:
            lines.append(f'- {warning}')
    return '\n'.join(lines).rstrip() + '\n'
