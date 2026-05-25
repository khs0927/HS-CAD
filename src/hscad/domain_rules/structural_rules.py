"""Structural plan-only rule checks."""
from __future__ import annotations

from hscad.core.evidence import ConfidenceScore
from hscad.core.models import FileizedDrawing
from hscad.domain_rules.base import DomainRuleEngine, DomainRuleResult, RuleStatus, warning_result


class StructuralRuleEngine(DomainRuleEngine):
    engine_id = "structural"

    def evaluate(self, drawing: FileizedDrawing) -> list[DomainRuleResult]:
        layers = {entity.layer for entity in drawing.entities}
        if "COL" not in layers and "CEN" not in layers:
            return [warning_result("STRUCT_GRID_OR_COLUMN_MISSING", "No COL or CEN layer detected", layers=sorted(layers))]
        return [
            DomainRuleResult(
                rule_id="STRUCT_BASIC_REFERENCE_PRESENCE",
                status=RuleStatus.PASS,
                confidence=ConfidenceScore.high("structural reference layer detected"),
                recommended_action="no_action",
                payload={"layers": sorted(layers)},
            )
        ]
