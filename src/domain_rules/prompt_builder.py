from __future__ import annotations

from typing import Any

from src.domain_rules.models import DrawingRuleReview, DomainRuleKnowledgePack


def build_system_drafting_constraints(
    knowledge_packs: list[DomainRuleKnowledgePack],
    review: DrawingRuleReview | None = None,
) -> str:
    """Build the rule-constrained drafting prompt for downstream AI agents."""
    lines: list[str] = [
        'SYSTEM DRAFTING CONSTRAINTS',
        '',
        'You are operating inside HS-CAD.',
        'The main authority is the domain rule knowledge extracted from XiCAD, ArchiOffice, and HS-Steel.',
        'ZWCAD COM is only an execution channel. It is not the design authority.',
        '',
        'GLOBAL SAFETY RULES',
        '- Never mutate the original DWG directly.',
        '- Always prefer review-gated plans and SaveAs outputs for modifications.',
        '- Treat drawing analysis evidence and domain rules as constraints before proposing geometry changes.',
        '- If a rule source is missing or not loaded, ask for verification rather than inventing dimensions.',
        '',
        'DOMAIN KNOWLEDGE SOURCES',
    ]
    for pack in knowledge_packs:
        summary = pack.summary
        lines.append(f'- {pack.source}: {pack.title}')
        for key, value in summary.items():
            lines.append(f'  - {key}: {value}')
        for warning in pack.warnings:
            lines.append(f'  - warning: {warning}')
    if review:
        lines += ['', 'FINDINGS TO RESPECT']
        for finding in review.findings:
            lines.append(f'- [{finding.source}:{finding.rule_id}] {finding.title}: {finding.recommendation or finding.message}')
        lines += ['', 'ALLOWED NEXT ACTIONS']
        for action in review.action_candidates:
            lines.append(f'- [{action.source}:{action.action_id}] {action.title} | risk={action.risk} | review={action.required_review}')
        lines += ['', 'PROMPT CONSTRAINTS']
        for item in review.prompt_constraints:
            lines.append(f'- {item}')
    return '\n'.join(lines).rstrip() + '\n'


def build_review_markdown(review: DrawingRuleReview, *, prompt: str | None = None) -> str:
    lines: list[str] = [
        '# HS-CAD Domain Rule Review',
        '',
        f'- Task: {review.task}',
        f'- Finding count: {len(review.findings)}',
        f'- Action candidate count: {len(review.action_candidates)}',
        '',
        '## Findings',
    ]
    if not review.findings:
        lines.append('- None')
    for item in review.findings:
        lines.append(f'- **{item.source}:{item.rule_id}** [{item.severity}] {item.title}')
        lines.append(f'  - {item.message}')
        if item.recommendation:
            lines.append(f'  - Recommendation: {item.recommendation}')
    lines += ['', '## Action candidates']
    if not review.action_candidates:
        lines.append('- None')
    for item in review.action_candidates:
        lines.append(f'- **{item.source}:{item.action_id}** {item.title}')
        lines.append(f'  - Risk: {item.risk}')
        lines.append(f'  - Reason: {item.reason}')
        if item.command_hint:
            lines.append(f'  - Command hint: `{item.command_hint}`')
    lines += ['', '## Prompt constraints']
    for item in review.prompt_constraints:
        lines.append(f'- {item}')
    if review.warnings:
        lines += ['', '## Warnings']
        for item in review.warnings:
            lines.append(f'- {item}')
    if prompt:
        lines += ['', '## System drafting constraints prompt', '', '```text', prompt.rstrip(), '```']
    return '\n'.join(lines).rstrip() + '\n'
