"""Energy/envelope plan-only rule checks."""
from __future__ import annotations

from hscad.core.evidence import ConfidenceScore
from hscad.core.models import FileizedDrawing
from hscad.domain_rules.base import DomainRuleEngine, DomainRuleResult, RuleStatus, warning_result


class EnergyRuleEngine(DomainRuleEngine):
    engine_id = "energy"

    def evaluate(self, drawing: FileizedDrawing) -> list[DomainRuleResult]:
        layers = {entity.layer for entity in drawing.entities}
        if not layers.intersection({"WIN", "WINBAR", "WINELE", "WAL1", "WAL2", "WAL3"}):
            return [warning_result("ENERGY_ENVELOPE_EVIDENCE_MISSING", "No envelope layer evidence detected", layers=sorted(layers))]
        return [
            DomainRuleResult(
                rule_id="ENERGY_ENVELOPE_EVIDENCE_PRESENT",
                status=RuleStatus.REVIEW,
                confidence=ConfidenceScore.medium("envelope evidence exists but U-value/material metadata is required"),
                recommended_action="attach_material_and_region_metadata",
                payload={"layers": sorted(layers)},
            )
        ]
