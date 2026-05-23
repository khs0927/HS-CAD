from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

RuleSource = Literal['xicad', 'archioffice', 'hssteel', 'combined']
ActionRisk = Literal['read_only', 'review_required', 'mutation_candidate', 'blocked']


@dataclass(frozen=True)
class DomainRuleFinding:
    source: RuleSource
    rule_id: str
    title: str
    severity: str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    recommendation: str = ''

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DraftingActionCandidate:
    source: RuleSource
    action_id: str
    title: str
    risk: ActionRisk
    reason: str
    command_hint: str = ''
    params: dict[str, Any] = field(default_factory=dict)
    required_review: bool = True
    save_as_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DomainRuleKnowledgePack:
    source: RuleSource
    title: str
    summary: dict[str, Any]
    rules: list[dict[str, Any]] = field(default_factory=list)
    assets: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DrawingRuleReview:
    task: str
    findings: list[DomainRuleFinding]
    action_candidates: list[DraftingActionCandidate]
    prompt_constraints: list[str]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'task': self.task,
            'findings': [item.to_dict() for item in self.findings],
            'action_candidates': [item.to_dict() for item in self.action_candidates],
            'prompt_constraints': self.prompt_constraints,
            'warnings': self.warnings,
        }
