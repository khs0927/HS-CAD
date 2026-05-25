"""Domain rule interfaces. All results are plan-only by default."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from hscad.core.evidence import Evidence, make_evidence
from hscad.core.models import FileizedDrawing


class RuleStatus(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    REVIEW = "review"


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    status: RuleStatus
    confidence: float
    message: str
    evidence_ids: list[str] = field(default_factory=list)
    recommended_action: str = "review_only"
    data: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "status": self.status.value,
            "confidence": self.confidence,
            "message": self.message,
            "evidence_ids": self.evidence_ids,
            "recommended_action": self.recommended_action,
            "data": self.data,
            "plan_only": True,
            "cad_execution": False,
        }

    def as_evidence(self) -> Evidence:
        return make_evidence(
            f"rule.{self.rule_id}",
            "domain_rule_result",
            self.message,
            module="hscad.domain_rules",
            source_id=self.rule_id,
            confidence=self.confidence,
            reason=self.status.value,
            data=self.to_record(),
        )


class DomainRule(Protocol):
    rule_id: str
    def evaluate(self, drawing: FileizedDrawing) -> RuleResult: ...
