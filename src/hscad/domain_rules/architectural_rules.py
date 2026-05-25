"""Architectural plan-only rule checks."""
from __future__ import annotations

from hscad.core.evidence import ConfidenceScore
from hscad.core.models import FileizedDrawing
from hscad.domain_rules.base import DomainRuleEngine, DomainRuleResult, RuleStatus, warning_result


class ArchitecturalRuleEngine(DomainRuleEngine):
    engine_id = "architectural"

    def evaluate(self, drawing: FileizedDrawing) -> list[DomainRuleResult]:
        layers = {entity.layer for entity in drawing.entities}
        results: list[DomainRuleResult] = []
        if not layers.intersection({"WAL1", "WAL2", "WAL3", "WAL_HATCH"}):
            results.append(warning_result("ARCH_WALL_LAYER_MISSING", "No canonical wall layer detected", layers=sorted(layers)))
        if not layers.intersection({"DOOR", "WIN", "WINBAR"}):
            results.append(warning_result("ARCH_OPENING_LAYER_MISSING", "No canonical door/window layer detected", layers=sorted(layers)))
        if not results:
            results.append(
                DomainRuleResult(
                    rule_id="ARCH_BASIC_LAYER_PRESENCE",
                    status=RuleStatus.PASS,
                    confidence=ConfidenceScore.high("canonical architectural layers detected"),
                    recommended_action="no_action",
                    payload={"layers": sorted(layers)},
                )
            )
        return results
