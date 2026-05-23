from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from src.execution.xicad_alias_classifier import XiCADAliasClassification, classify_xicad_alias


@dataclass(frozen=True)
class XiCADAliasPlanStep:
    order: int
    source_step_id: str
    source_decision_id: str
    command_hint: str
    command_type: str
    classification: XiCADAliasClassification

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["classification"] = self.classification.to_dict()
        return data


@dataclass(frozen=True)
class XiCADAliasAllowlistPlan:
    source_command_plan: str
    status: str
    steps: list[XiCADAliasPlanStep]
    blocked_aliases: list[str] = field(default_factory=list)
    review_required_aliases: list[str] = field(default_factory=list)
    dry_run_allowed_aliases: list[str] = field(default_factory=list)
    execution_allowed_aliases: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_command_plan": self.source_command_plan,
            "status": self.status,
            "steps": [step.to_dict() for step in self.steps],
            "blocked_aliases": self.blocked_aliases,
            "review_required_aliases": self.review_required_aliases,
            "dry_run_allowed_aliases": self.dry_run_allowed_aliases,
            "execution_allowed_aliases": self.execution_allowed_aliases,
            "warnings": self.warnings,
        }


def build_xicad_alias_allowlist_plan(
    command_plan: dict[str, Any],
    *,
    source_command_plan: str = "command-plan",
) -> XiCADAliasAllowlistPlan:
    steps: list[XiCADAliasPlanStep] = []
    blocked: list[str] = []
    review_required: list[str] = []
    dry_run_allowed: list[str] = []
    execution_allowed: list[str] = []
    warnings: list[str] = []

    for item in command_plan.get("dry_run_steps") or []:
        command_type = str(item.get("command_type") or "")
        command_hint = str(item.get("command_hint") or "")

        if command_type != "xicad-safe-plan" and "xicad" not in command_hint.lower():
            continue

        classification = classify_xicad_alias(command_hint)

        step = XiCADAliasPlanStep(
            order=len(steps) + 1,
            source_step_id=str(item.get("step_id") or ""),
            source_decision_id=str(item.get("source_decision_id") or ""),
            command_hint=command_hint,
            command_type=command_type,
            classification=classification,
        )
        steps.append(step)

        alias = classification.alias or "<missing>"
        if classification.blocked_reason:
            blocked.append(alias)
        elif classification.policy.requires_human_review:
            review_required.append(alias)

        if classification.allowed_for_dry_run:
            dry_run_allowed.append(alias)

        if classification.allowed_for_execution:
            execution_allowed.append(alias)

    if execution_allowed:
        warnings.append("Execution allowed aliases should normally be empty at this stage.")

    if blocked:
        status = "blocked"
    elif review_required:
        status = "review_required"
    else:
        status = "dry_run_allowed"

    return XiCADAliasAllowlistPlan(
        source_command_plan=source_command_plan,
        status=status,
        steps=steps,
        blocked_aliases=_dedupe(blocked),
        review_required_aliases=_dedupe(review_required),
        dry_run_allowed_aliases=_dedupe(dry_run_allowed),
        execution_allowed_aliases=_dedupe(execution_allowed),
        warnings=warnings,
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out
