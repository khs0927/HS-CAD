from __future__ import annotations

from typing import Any

from src.domain_rules.review_gate_models import ReviewGateCheck, ReviewGatePackage


def build_review_gate_package(command_plan: dict[str, Any], *, source: str = 'command-plan') -> ReviewGatePackage:
    task = str(command_plan.get('task') or 'domain rule review gate')
    checks: list[ReviewGateCheck] = []
    blocked_reasons: list[str] = list(command_plan.get('blocked_reasons') or [])
    warnings: list[str] = list(command_plan.get('warnings') or [])

    dry_run_steps = list(command_plan.get('dry_run_steps') or [])
    queue = dict(command_plan.get('execution_queue_candidate') or {})
    review_table = list(command_plan.get('review_table') or [])

    checks.append(_check_has_review_table(review_table))
    checks.append(_check_no_direct_execution(queue))
    checks.append(_check_save_as_required(queue))
    checks.append(_check_approval_required(queue))
    checks.append(_check_dry_run_steps(dry_run_steps))

    for step in dry_run_steps:
        if step.get('risk') == 'blocked' or step.get('blocked_reason'):
            reason = str(step.get('blocked_reason') or step.get('reason') or 'A dry-run step is blocked')
            blocked_reasons.append(reason)

    if blocked_reasons or any(check.status == 'fail' for check in checks):
        status = 'blocked'
    elif any(check.status == 'needs_review' for check in checks):
        status = 'awaiting_human_review'
    else:
        status = 'ready_for_dry_run_only'

    return ReviewGatePackage(
        task=task,
        source_command_plan=source,
        status=status,
        checks=checks,
        signoff_required=_signoff_required(),
        allowed_next_steps=_allowed_next_steps(status),
        blocked_reasons=_dedupe(blocked_reasons),
        warnings=warnings,
    )


def _check_has_review_table(review_table: list[dict[str, Any]]) -> ReviewGateCheck:
    if review_table:
        return ReviewGateCheck('review-table', 'Review table exists', 'pass', 'Review table rows are available.', {'row_count': len(review_table)})
    return ReviewGateCheck('review-table', 'Review table exists', 'fail', 'No review table rows were found.')


def _check_no_direct_execution(queue: dict[str, Any]) -> ReviewGateCheck:
    status = str(queue.get('status') or '')
    if status in {'executing', 'executed', 'auto_execute'}:
        return ReviewGateCheck('no-direct-execution', 'No direct execution state', 'fail', f'Queue status is not safe: {status}', {'queue_status': status})
    return ReviewGateCheck('no-direct-execution', 'No direct execution state', 'pass', 'Queue is not in an execution state.', {'queue_status': status})


def _check_save_as_required(queue: dict[str, Any]) -> ReviewGateCheck:
    if queue.get('save_as_required') is True:
        return ReviewGateCheck('save-as-required', 'SaveAs is required', 'pass', 'Queue candidate requires SaveAs.')
    return ReviewGateCheck('save-as-required', 'SaveAs is required', 'fail', 'Queue candidate does not require SaveAs.')


def _check_approval_required(queue: dict[str, Any]) -> ReviewGateCheck:
    if queue.get('approval_required') is True:
        return ReviewGateCheck('approval-required', 'Human approval is required', 'pass', 'Queue candidate requires human approval.')
    return ReviewGateCheck('approval-required', 'Human approval is required', 'fail', 'Queue candidate does not require human approval.')


def _check_dry_run_steps(steps: list[dict[str, Any]]) -> ReviewGateCheck:
    if not steps:
        return ReviewGateCheck('dry-run-steps', 'Dry-run steps exist', 'needs_review', 'No dry-run steps exist; manual review may still be valid.')
    risky = [step for step in steps if step.get('risk') not in {'review_required', 'mutation_gated', 'blocked'}]
    if risky:
        return ReviewGateCheck('dry-run-steps', 'Dry-run steps are classified', 'needs_review', 'Some steps have unusual risk classification.', {'count': len(risky)})
    return ReviewGateCheck('dry-run-steps', 'Dry-run steps are classified', 'pass', 'Dry-run steps are present and classified.', {'count': len(steps)})


def _signoff_required() -> list[str]:
    return [
        'Confirm original DWG will not be modified.',
        'Confirm SaveAs target path before any future execution.',
        'Confirm domain-rule findings have been reviewed.',
        'Confirm dry-run outputs match expected geometry/layer changes.',
        'Confirm a human operator explicitly approves execution.',
    ]


def _allowed_next_steps(status: str) -> list[str]:
    if status == 'blocked':
        return ['Resolve blocked reasons', 'Regenerate command plan', 'Re-run review gate']
    if status == 'awaiting_human_review':
        return ['Human review', 'Annotate review table', 'Regenerate plan if needed']
    return ['Run dry-run only', 'Collect dry-run output', 'Request human approval before any execution']


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            rows.append(value)
    return rows
