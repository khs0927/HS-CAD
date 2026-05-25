"""Fire-safety plan-only rule checks.

These checks are intentionally heuristic.  Project-specific legal criteria should
be added as explicit rule data, not hard-coded into CAD execution.
"""
from __future__ import annotations

from hscad.core.evidence import ConfidenceScore
from hscad.core.models import FileizedDrawing
from hscad.domain_rules.base import DomainRuleEngine, DomainRuleResult, RuleStatus, warning_result


class FireRuleEngine(DomainRuleEngine):
    engine_id = "fire"

    def evaluate(self, drawing: FileizedDrawing) -> list[DomainRuleResult]:
        layers = {entity.layer for entity in drawing.entities}
        results: list[DomainRuleResult] = []
        if not layers.intersection({"WIN", "WINBAR", "WINELE"}):
            results.append(warning_result("FIRE_WINDOW_EVIDENCE_MISSING", "No window evidence layer detected for firefighter-entry review", layers=sorted(layers)))
        if not layers.intersection({"DOOR", "DOOR_SWING"}):
            results.append(warning_result("FIRE_DOOR_EVIDENCE_MISSING", "No door evidence layer detected for egress review", layers=sorted(layers)))
        if results:
            return results
        return [
            DomainRuleResult(
                rule_id="FIRE_BASIC_OPENING_EVIDENCE_PRESENT",
                status=RuleStatus.REVIEW,
                confidence=ConfidenceScore.medium("opening layers exist but legal check requires project metadata"),
                recommended_action="manual_fire_code_review_required",
                payload={"layers": sorted(layers)},
            )
        ]
