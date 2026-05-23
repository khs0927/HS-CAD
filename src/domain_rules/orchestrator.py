from __future__ import annotations

from pathlib import Path
from typing import Any

from src.domain_rules.archioffice_rule_engine import ArchiOfficeRuleEngine
from src.domain_rules.hssteel_rule_engine import HSSteelRuleEngine
from src.domain_rules.models import DrawingRuleReview, DomainRuleFinding, DomainRuleKnowledgePack, DraftingActionCandidate
from src.domain_rules.prompt_builder import build_system_drafting_constraints
from src.domain_rules.xicad_rule_adapter import XiCADDomainRuleAdapter


class DomainRuleOrchestrator:
    """Combines XiCAD, ArchiOffice, and HS-Steel rules for modification planning."""

    def __init__(
        self,
        *,
        xicad_root: str | Path = 'C:/xicad',
        archioffice_root: str | Path | None = None,
        hssteel_root: str | Path | None = None,
    ):
        self.xicad = XiCADDomainRuleAdapter(xicad_root)
        self.archioffice = ArchiOfficeRuleEngine(archioffice_root)
        self.hssteel = HSSteelRuleEngine(hssteel_root)

    def build_knowledge_packs(self) -> list[DomainRuleKnowledgePack]:
        return [
            self.xicad.build_knowledge_pack(),
            self.archioffice.build_knowledge_pack(),
            self.hssteel.build_knowledge_pack(),
        ]

    def review_drawing(self, objects: list[dict[str, Any]], *, task: str = 'drawing modification review') -> DrawingRuleReview:
        findings: list[DomainRuleFinding] = []
        actions: list[DraftingActionCandidate] = []
        warnings: list[str] = []

        for engine in (self.xicad, self.archioffice, self.hssteel):
            try:
                # Add warnings from engine rules loading step
                pack = engine.build_knowledge_pack()
                if pack.warnings:
                    warnings.extend(pack.warnings)
            except Exception as exc:
                warnings.append(f'{engine.__class__.__name__} pack build failed: {exc}')

            try:
                engine_findings, engine_actions = engine.review_drawing(objects)
                findings.extend(engine_findings)
                actions.extend(engine_actions)
            except Exception as exc:
                warnings.append(f'{engine.__class__.__name__} review failed: {exc}')

        prompt_constraints = []
        for engine in (self.xicad, self.archioffice, self.hssteel):
            try:
                prompt_constraints.extend(engine.prompt_constraints())
            except Exception as exc:
                warnings.append(f'{engine.__class__.__name__} prompt constraints failed: {exc}')

        prompt_constraints.extend(
            [
                'Use domain-rule review before selecting any modifying command.',
                'Prefer rule-derived correction plans over raw geometry guessing.',
                'If XiCAD/ArchiOffice/HS-Steel disagree, stop and produce a review table instead of executing.',
            ]
        )
        return DrawingRuleReview(
            task=task,
            findings=findings,
            action_candidates=actions,
            prompt_constraints=_dedupe(prompt_constraints),
            warnings=warnings,
        )

    def build_constraint_prompt(self, objects: list[dict[str, Any]], *, task: str = 'drawing modification review') -> str:
        packs = self.build_knowledge_packs()
        review = self.review_drawing(objects, task=task)
        return build_system_drafting_constraints(packs, review)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            rows.append(value)
    return rows
