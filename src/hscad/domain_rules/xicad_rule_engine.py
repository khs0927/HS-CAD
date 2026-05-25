"""XiCAD rule engine boundary.

This module intentionally creates plans only. It never executes XiCAD aliases.
"""
from __future__ import annotations

from hscad.core.evidence import ConfidenceScore
from hscad.core.models import FileizedDrawing
from hscad.domain_rules.base import DomainRuleEngine, DomainRuleResult, RuleStatus


class XiCadRuleEngine(DomainRuleEngine):
    engine_id = "xicad"

    def evaluate(self, drawing: FileizedDrawing) -> list[DomainRuleResult]:
        return [
            DomainRuleResult(
                rule_id="XICAD_ALIAS_EXECUTION_DISABLED",
                status=RuleStatus.REVIEW,
                confidence=ConfidenceScore.high("XiCAD alias execution remains disabled by default"),
                recommended_action="generate_xicad_plan_only; require human approval before execution",
                payload={
                    "xicad_alias_execution_allowed_by_default": False,
                    "entity_count": len(drawing.entities),
                },
            )
        ]
