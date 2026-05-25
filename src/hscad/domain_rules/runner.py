from __future__ import annotations

from hscad.core.models import FileizedDrawing
from hscad.domain_rules.architectural_rules import WallLayerPresenceRule
from hscad.domain_rules.base import RuleResult
from hscad.domain_rules.energy_rules import EnvelopeEnergyReviewRule
from hscad.domain_rules.fire_rules import FireOpeningReviewRule
from hscad.domain_rules.structural_rules import StructuralLayerPresenceRule
from hscad.domain_rules.xicad_rule_engine import XiCadPlanOnlyRule


class DomainRuleRunner:
    def __init__(self) -> None:
        self.rules = [WallLayerPresenceRule(), StructuralLayerPresenceRule(), FireOpeningReviewRule(), EnvelopeEnergyReviewRule(), XiCadPlanOnlyRule()]

    def evaluate(self, drawing: FileizedDrawing) -> list[RuleResult]:
        return [rule.evaluate(drawing) for rule in self.rules]
