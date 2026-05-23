from __future__ import annotations

from pathlib import Path
from typing import Any

from src.domain_rules.models import DomainRuleFinding, DomainRuleKnowledgePack, DraftingActionCandidate
from src.integrations.xicad_rule_engine import XiCADRuleEngine


class XiCADDomainRuleAdapter:
    """Adapter that turns XiCADRuleEngine outputs into domain-rule review data."""

    def __init__(self, xicad_root: str | Path = 'C:/xicad'):
        self.xicad_root = Path(xicad_root)
        self.engine = XiCADRuleEngine(str(self.xicad_root))
        self.loaded = False

    def load(self) -> bool:
        self.loaded = self.engine.load_all_rules()
        return self.loaded

    def build_knowledge_pack(self) -> DomainRuleKnowledgePack:
        if not self.loaded:
            self.load()
        warnings: list[str] = []
        if not self.loaded:
            warnings.append(f'XiCAD root not found or rules not loaded: {self.xicad_root}')
        summary = {
            'root': str(self.xicad_root),
            'loaded': self.loaded,
            'wall_style_count': len(self.engine.wall_styles),
            'block_layer_rule_count': len(self.engine.block_layer_rules),
            'config_count': len(self.engine.configs),
            'shortkey_count': len(self.engine.shortkeys),
            'pgp_alias_count': len(self.engine.pgp_aliases),
            'steel_spec_count': len(self.engine.structural_steel_specs),
            'block_catalog_count': len(self.engine.block_catalog),
        }
        rules = [
            {'name': 'wall_styles', 'count': len(self.engine.wall_styles)},
            {'name': 'block_layer_rules', 'count': len(self.engine.block_layer_rules)},
            {'name': 'configs', 'count': len(self.engine.configs)},
            {'name': 'shortkeys', 'count': len(self.engine.shortkeys)},
            {'name': 'pgp_aliases', 'count': len(self.engine.pgp_aliases)},
        ]
        assets = [{'name': key, 'kind': 'block'} for key in list(self.engine.block_catalog.keys())[:200]]
        return DomainRuleKnowledgePack(
            source='xicad',
            title='XiCAD multi-dimensional rule engine',
            summary=summary,
            rules=rules,
            assets=assets,
            warnings=warnings,
        )

    def review_drawing(self, objects: list[dict[str, Any]]) -> tuple[list[DomainRuleFinding], list[DraftingActionCandidate]]:
        if not self.loaded:
            self.load()
        findings: list[DomainRuleFinding] = []
        actions: list[DraftingActionCandidate] = []
        layers = {str(item.get('layer') or '0') for item in objects}
        known_layers = {str(rule.get('layer')) for rule in self.engine.block_layer_rules.values() if isinstance(rule, dict) and rule.get('layer')}
        if known_layers:
            unknown_layers = sorted(layer for layer in layers if layer not in known_layers and layer != '0')
            if unknown_layers:
                findings.append(
                    DomainRuleFinding(
                        source='xicad',
                        rule_id='XI-LAYER-001',
                        title='Layers outside XiCAD block-layer rules detected',
                        severity='warning',
                        message='Some scanned layers are not present in parsed XiCAD block-layer rules.',
                        evidence={'unknown_layers': unknown_layers[:50], 'unknown_count': len(unknown_layers)},
                        recommendation='Review layer mapping against xiBlkLayerSet before mutation.',
                    )
                )
                actions.append(
                    DraftingActionCandidate(
                        source='xicad',
                        action_id='XI-ACTION-LAYER-MAP',
                        title='Prepare XiCAD layer mapping review',
                        risk='review_required',
                        reason='XiCAD rule-based modification requires verified layer mappings.',
                        command_hint='xicad-safe-plan --alias LAYER-MAP',
                    )
                )
        if self.loaded and self.engine.wall_styles:
            findings.append(
                DomainRuleFinding(
                    source='xicad',
                    rule_id='XI-WALL-STYLE-001',
                    title='XiCAD wall styles available for wall correction decisions',
                    severity='info',
                    message='Parsed wall style groups can be used to select total wall thickness and core structure thickness.',
                    evidence={'wall_style_count': len(self.engine.wall_styles)},
                    recommendation='Use parsed xiDrawWall styles before generating or correcting wall multiline geometry.',
                )
            )
        return findings, actions

    def prompt_constraints(self) -> list[str]:
        return [
            'Use XiCAD wall, layer, config, shortcut, steel data, and block catalog rules as drafting constraints.',
            'Do not generate wall or block geometry that contradicts parsed XiCAD rule data.',
            'XiCAD command execution must be planned first and remain review-gated.',
        ]
