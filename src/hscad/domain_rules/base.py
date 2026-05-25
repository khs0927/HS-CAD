"""Plan-only domain rule engine interfaces."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from hscad.core.evidence import ConfidenceScore, Evidence, EvidenceKind, EvidenceSource
from hscad.core.models import FileizedDrawing


class RuleStatus(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    REVIEW = "review"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class DomainRuleResult:
    rule_id: str
    status: RuleStatus | str
    confidence: ConfidenceScore
    evidence: list[Evidence] = field(default_factory=list)
    recommended_action: str = "manual_review_required"
    plan_only: bool = True
    payload: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "status": self.status.value if isinstance(self.status, RuleStatus) else str(self.status),
            "confidence": {
                "value": self.confidence.value,
                "reason": self.confidence.reason,
                "method": self.confidence.method,
            },
            "evidence": [item.to_record() for item in self.evidence],
            "recommended_action": self.recommended_action,
            "plan_only": self.plan_only,
            "payload": self.payload,
        }

    def as_evidence(self) -> Evidence:
        return Evidence(
            source=EvidenceSource.DOMAIN_RULE,
            kind=EvidenceKind.RULE_RESULT,
            entity_id=f"rule:{self.rule_id}",
            payload=self.to_record(),
            confidence=self.confidence,
            tags=["domain_rule", "plan_only"],
        )


class DomainRuleEngine(ABC):
    engine_id = "base"

    @abstractmethod
    def evaluate(self, drawing: FileizedDrawing) -> list[DomainRuleResult]:
        raise NotImplementedError


def warning_result(rule_id: str, message: str, *, confidence: float = 0.6, **payload: Any) -> DomainRuleResult:
    ev = Evidence.warning(message, source=EvidenceSource.DOMAIN_RULE, rule_id=rule_id, **payload)
    return DomainRuleResult(
        rule_id=rule_id,
        status=RuleStatus.WARNING,
        confidence=ConfidenceScore(confidence, reason=message, method="rule_heuristic"),
        evidence=[ev],
        payload={"message": message, **payload},
    )
