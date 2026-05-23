from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

GateStatus = Literal['blocked', 'awaiting_human_review', 'ready_for_dry_run_only']
GateCheckStatus = Literal['pass', 'fail', 'needs_review']


@dataclass(frozen=True)
class ReviewGateCheck:
    check_id: str
    title: str
    status: GateCheckStatus
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewGatePackage:
    task: str
    source_command_plan: str
    status: GateStatus
    checks: list[ReviewGateCheck]
    signoff_required: list[str]
    allowed_next_steps: list[str]
    blocked_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'task': self.task,
            'source_command_plan': self.source_command_plan,
            'status': self.status,
            'checks': [item.to_dict() for item in self.checks],
            'signoff_required': self.signoff_required,
            'allowed_next_steps': self.allowed_next_steps,
            'blocked_reasons': self.blocked_reasons,
            'warnings': self.warnings,
        }
