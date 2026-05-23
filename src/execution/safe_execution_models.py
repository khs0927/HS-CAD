from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ExecutionMode = Literal["dry_run", "approved_copy_execution"]
ExecutionStatus = Literal[
    "blocked",
    "ready_for_dry_run",
    "ready_for_approved_copy_execution",
    "executed_on_copy",
    "failed",
]
ExecutionRisk = Literal["read_only", "review_required", "mutation_on_copy", "blocked"]


@dataclass(frozen=True)
class SafeExecutionStep:
    order: int
    step_id: str
    title: str
    mode: ExecutionMode
    risk: ExecutionRisk
    command_type: str
    command_hint: str
    source_plan_step_id: str = ""
    source_decision_id: str = ""
    preconditions: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    blocked_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SafeExecutionPackage:
    task: str
    source_command_plan: str
    source_review_gate: str
    mode: ExecutionMode
    status: ExecutionStatus
    save_as_required: bool
    operator_approved: bool
    original_dwg: str
    working_copy_dwg: str
    save_as_target: str
    steps: list[SafeExecutionStep]
    blocked_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    required_confirmations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "source_command_plan": self.source_command_plan,
            "source_review_gate": self.source_review_gate,
            "mode": self.mode,
            "status": self.status,
            "save_as_required": self.save_as_required,
            "operator_approved": self.operator_approved,
            "original_dwg": self.original_dwg,
            "working_copy_dwg": self.working_copy_dwg,
            "save_as_target": self.save_as_target,
            "steps": [step.to_dict() for step in self.steps],
            "blocked_reasons": self.blocked_reasons,
            "warnings": self.warnings,
            "required_confirmations": self.required_confirmations,
        }
