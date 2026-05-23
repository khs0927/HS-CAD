from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

PlanStatus = Literal['draft', 'blocked', 'ready_for_human_review']
PlanRisk = Literal['read_only', 'review_required', 'mutation_gated', 'blocked']


@dataclass(frozen=True)
class DryRunCommandStep:
    order: int
    step_id: str
    title: str
    risk: PlanRisk
    command_type: str
    command_hint: str
    params: dict[str, Any] = field(default_factory=dict)
    source_decision_id: str = ''
    reason: str = ''
    preconditions: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    blocked_reason: str = ''

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionQueueCandidate:
    queue_id: str
    status: str
    steps: list[DryRunCommandStep]
    approval_required: bool = True
    save_as_required: bool = True
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'queue_id': self.queue_id,
            'status': self.status,
            'steps': [step.to_dict() for step in self.steps],
            'approval_required': self.approval_required,
            'save_as_required': self.save_as_required,
            'notes': self.notes,
        }


@dataclass(frozen=True)
class DomainRuleCommandPlan:
    task: str
    source_decision_package: str
    status: PlanStatus
    dry_run_steps: list[DryRunCommandStep]
    review_table: list[dict[str, Any]]
    execution_queue_candidate: ExecutionQueueCandidate
    blocked_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'task': self.task,
            'source_decision_package': self.source_decision_package,
            'status': self.status,
            'dry_run_steps': [step.to_dict() for step in self.dry_run_steps],
            'review_table': self.review_table,
            'execution_queue_candidate': self.execution_queue_candidate.to_dict(),
            'blocked_reasons': self.blocked_reasons,
            'warnings': self.warnings,
        }
