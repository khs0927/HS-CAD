"""Run all plan-only domain rules."""
from __future__ import annotations

from hscad.core.models import FileizedDrawing
from hscad.domain_rules.architectural_rules import ArchitecturalRuleEngine
from hscad.domain_rules.base import DomainRuleResult
from hscad.domain_rules.energy_rules import EnergyRuleEngine
from hscad.domain_rules.fire_rules import FireRuleEngine
from hscad.domain_rules.structural_rules import StructuralRuleEngine
from hscad.domain_rules.xicad_rule_engine import XiCadRuleEngine


class DomainRuleRunner:
    def __init__(self) -> None:
        self.engines = [
            ArchitecturalRuleEngine(),
            StructuralRuleEngine(),
            FireRuleEngine(),
            EnergyRuleEngine(),
            XiCadRuleEngine(),
        ]

    def evaluate(self, drawing: FileizedDrawing) -> list[DomainRuleResult]:
        results: list[DomainRuleResult] = []
        for engine in self.engines:
            results.extend(engine.evaluate(drawing))
        return results
