from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

DecisionStatus = Literal['ready_for_review', 'blocked', 'needs_more_evidence']
DecisionPriority = Literal['critical', 'high', 'medium', 'low']


@dataclass(frozen=True)
class ModificationDecision:
    decision_id: str
    title: str
    status: DecisionStatus
    priority: DecisionPriority
    reason: str
    rule_sources: list[str]
    evidence_refs: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    command_hints: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModificationDecisionPackage:
    task: str
    source: str
    status: DecisionStatus
    decisions: list[ModificationDecision]
    blocked_reasons: list[str]
    required_evidence: list[str]
    review_checklist: list[str]
    system_prompt: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'task': self.task,
            'source': self.source,
            'status': self.status,
            'decisions': [item.to_dict() for item in self.decisions],
            'blocked_reasons': self.blocked_reasons,
            'required_evidence': self.required_evidence,
            'review_checklist': self.review_checklist,
            'system_prompt': self.system_prompt,
            'warnings': self.warnings,
        }
