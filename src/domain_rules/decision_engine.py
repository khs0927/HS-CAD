from __future__ import annotations

from typing import Any

from src.domain_rules.decision_models import ModificationDecision, ModificationDecisionPackage
from src.domain_rules.orchestrator import DomainRuleOrchestrator
from src.domain_rules.prompt_builder import build_system_drafting_constraints


class DomainRuleDecisionEngine:
    """Turn analyzed drawing objects into review-gated modification decisions."""

    def __init__(self, orchestrator: DomainRuleOrchestrator | None = None):
        self.orchestrator = orchestrator or DomainRuleOrchestrator()

    def decide(self, objects: list[dict[str, Any]], *, task: str = 'drawing modification', source: str = 'objects') -> ModificationDecisionPackage:
        packs = self.orchestrator.build_knowledge_packs()
        review = self.orchestrator.review_drawing(objects, task=task)
        prompt = build_system_drafting_constraints(packs, review)

        decisions: list[ModificationDecision] = []
        required_evidence: list[str] = []
        blocked_reasons: list[str] = []

        if not objects:
            blocked_reasons.append('No analyzed drawing objects were provided.')
            required_evidence.extend(['DWG object scan', 'layer counts', 'text evidence', 'dimension evidence'])

        for finding in review.findings:
            if finding.severity in {'warning', 'error'}:
                decisions.append(
                    ModificationDecision(
                        decision_id=f'finding:{finding.source}:{finding.rule_id}',
                        title=f'Review finding: {finding.title}',
                        status='ready_for_review',
                        priority='high' if finding.severity == 'error' else 'medium',
                        reason=finding.recommendation or finding.message,
                        rule_sources=[finding.source],
                        evidence_refs=[finding.rule_id],
                        next_steps=['Review finding evidence', 'Resolve before mutation if it affects geometry or layers'],
                        warnings=[finding.message],
                    )
                )

        for action in review.action_candidates:
            status = 'ready_for_review' if action.risk != 'blocked' else 'blocked'
            if action.risk == 'blocked':
                blocked_reasons.append(action.reason)
            decisions.append(
                ModificationDecision(
                    decision_id=f'action:{action.source}:{action.action_id}',
                    title=action.title,
                    status=status,
                    priority=_priority_from_risk(action.risk),
                    reason=action.reason,
                    rule_sources=[action.source],
                    evidence_refs=list(action.params.keys()),
                    next_steps=['Create dry-run plan', 'Produce review table', 'Only execute after approval and SaveAs'],
                    command_hints=[action.command_hint] if action.command_hint else [],
                    warnings=[] if action.required_review else ['Action is not marked review-required; verify policy.'],
                    metadata={'risk': action.risk, 'save_as_required': action.save_as_required},
                )
            )

        if not decisions and objects:
            decisions.append(
                ModificationDecision(
                    decision_id='decision:baseline-review',
                    title='No blocking domain-rule issue detected in synthetic review',
                    status='ready_for_review',
                    priority='low',
                    reason='Domain engines did not produce review-blocking findings. Continue with dry-run planning.',
                    rule_sources=['combined'],
                    next_steps=['Generate dry-run action list', 'Compare against XiCAD/ArchiOffice/HS-Steel constraints'],
                )
            )

        status = 'blocked' if blocked_reasons else ('needs_more_evidence' if required_evidence else 'ready_for_review')
        return ModificationDecisionPackage(
            task=task,
            source=source,
            status=status,
            decisions=decisions,
            blocked_reasons=_dedupe(blocked_reasons),
            required_evidence=_dedupe(required_evidence),
            review_checklist=_review_checklist(),
            system_prompt=prompt,
            warnings=review.warnings,
        )


def _priority_from_risk(risk: str) -> str:
    if risk == 'blocked':
        return 'critical'
    if risk == 'mutation_candidate':
        return 'high'
    if risk == 'review_required':
        return 'medium'
    return 'low'


def _review_checklist() -> list[str]:
    return [
        'Confirm the source drawing is not the original production DWG or use SaveAs.',
        'Confirm XiCAD/ArchiOffice/HS-Steel rule packs were loaded or warnings were reviewed.',
        'Confirm layer, text, dimension, and block evidence are sufficient for the requested change.',
        'Run dry-run before any modifying command.',
        'Require human approval before execution.',
    ]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            rows.append(value)
    return rows
