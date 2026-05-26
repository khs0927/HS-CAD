from __future__ import annotations

from typing import Any

from src.domain_rules.command_plan_models import DomainRuleCommandPlan, DryRunCommandStep, ExecutionQueueCandidate


def build_command_plan(decision_package: dict[str, Any], *, source: str = 'decision-package') -> DomainRuleCommandPlan:
    """Convert a domain-rule decision package into dry-run command planning data."""
    task = str(decision_package.get('task') or 'domain rule command planning')
    blocked_reasons = list(decision_package.get('blocked_reasons') or [])
    warnings = list(decision_package.get('warnings') or [])
    decisions = list(decision_package.get('decisions') or [])

    steps: list[DryRunCommandStep] = []
    order = 1

    if blocked_reasons:
        for reason in blocked_reasons:
            steps.append(
                DryRunCommandStep(
                    order=order,
                    step_id=f'blocked-{order}',
                    title='Blocked before command planning',
                    risk='blocked',
                    command_type='none',
                    command_hint='',
                    reason=reason,
                    blocked_reason=reason,
                    preconditions=['Provide missing evidence before dry-run planning'],
                )
            )
            order += 1

    for decision in decisions:
        decision_id = str(decision.get('decision_id') or f'decision-{order}')
        status = str(decision.get('status') or '')
        command_hints = list(decision.get('command_hints') or [])
        title = str(decision.get('title') or decision_id)
        reason = str(decision.get('reason') or '')
        if status == 'blocked':
            steps.append(
                DryRunCommandStep(
                    order=order,
                    step_id=f'blocked-{decision_id}',
                    title=title,
                    risk='blocked',
                    command_type='none',
                    command_hint='',
                    source_decision_id=decision_id,
                    reason=reason,
                    blocked_reason=reason or 'Decision is blocked',
                )
            )
            order += 1
            continue

        if command_hints:
            for hint in command_hints:
                steps.append(
                    DryRunCommandStep(
                        order=order,
                        step_id=f'dry-run-{order}',
                        title=title,
                        risk='mutation_gated',
                        command_type=_command_type(hint),
                        command_hint=str(hint),
                        source_decision_id=decision_id,
                        reason=reason,
                        preconditions=_default_preconditions(),
                        expected_outputs=['dry-run action list', 'review table row'],
                    )
                )
                order += 1
        else:
            steps.append(
                DryRunCommandStep(
                    order=order,
                    step_id=f'review-{order}',
                    title=title,
                    risk='review_required',
                    command_type='review-only',
                    command_hint='manual-review-table',
                    source_decision_id=decision_id,
                    reason=reason,
                    preconditions=['Human reviewer must classify whether a CAD command is needed'],
                    expected_outputs=['review table row'],
                )
            )
            order += 1

    if not steps:
        steps.append(
            DryRunCommandStep(
                order=1,
                step_id='baseline-review',
                title='Baseline review only',
                risk='review_required',
                command_type='review-only',
                command_hint='manual-review-table',
                reason='No commandable decision was found.',
                preconditions=['Confirm decision package is complete'],
                expected_outputs=['review note'],
            )
        )

    review_table = [_review_row(step) for step in steps]
    queue_steps = [step for step in steps if step.risk == 'mutation_gated']
    status = 'blocked' if any(step.risk == 'blocked' for step in steps) else 'ready_for_human_review'
    queue = ExecutionQueueCandidate(
        queue_id='domain-rule-execution-candidate',
        status='blocked' if status == 'blocked' else 'awaiting_approval',
        steps=queue_steps,
        notes=[
            'This is not an execution command.',
            'Run dry-run first, then require explicit approval and SaveAs before execution.',
        ],
    )
    return DomainRuleCommandPlan(
        task=task,
        source_decision_package=source,
        status=status,
        dry_run_steps=steps,
        review_table=review_table,
        execution_queue_candidate=queue,
        blocked_reasons=blocked_reasons,
        warnings=warnings,
    )


def _command_type(hint: str) -> str:
    lowered = hint.lower()
    if 'xicad' in lowered:
        return 'xicad-safe-plan'
    if 'hscad-tool-plan' in lowered:
        return 'workflow-plan'
    if 'run-command' in lowered:
        return 'json-command-dry-run'
    return 'dry-run-hint'


def _default_preconditions() -> list[str]:
    return [
        'Original DWG must not be mutated.',
        'Use copied drawing or SaveAs target.',
        'Domain rule findings must be reviewed.',
        'Dry-run output must be approved before execution.',
    ]


def _review_row(step: DryRunCommandStep) -> dict[str, Any]:
    return {
        'order': step.order,
        'step_id': step.step_id,
        'title': step.title,
        'risk': step.risk,
        'command_type': step.command_type,
        'command_hint': step.command_hint,
        'source_decision_id': step.source_decision_id,
        'reason': step.reason,
        'blocked_reason': step.blocked_reason,
    }
