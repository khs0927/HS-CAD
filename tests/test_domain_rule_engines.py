from __future__ import annotations

from src.domain_rules.archioffice_rule_engine import ArchiOfficeRuleEngine
from src.domain_rules.hssteel_rule_engine import HSSteelRuleEngine
from src.domain_rules.orchestrator import DomainRuleOrchestrator
from src.domain_rules.prompt_builder import build_system_drafting_constraints
from src.domain_rules.xicad_rule_adapter import XiCADDomainRuleAdapter


SYNTHETIC_OBJECTS = [
    {'object_name': 'AcDbPolyline', 'entity_type': 'POLYLINE', 'closed': True, 'layer': 'WAL1'},
    {'object_name': 'AcDbBlockReference', 'entity_type': 'INSERT', 'layer': '0', 'name': 'H-300x150'},
    {'object_name': 'AcDbText', 'entity_type': 'TEXT', 'layer': 'ROOM-TEXT', 'text': 'ROOM 101'},
]


def test_xicad_adapter_builds_pack_without_local_xicad():
    pack = XiCADDomainRuleAdapter('Z:/missing-xicad-for-test').build_knowledge_pack()

    assert pack.source == 'xicad'
    assert pack.summary['loaded'] is False
    assert pack.warnings


def test_archioffice_engine_reviews_layer_evidence():
    findings, actions = ArchiOfficeRuleEngine().review_drawing([{'layer': '0', 'entity_type': 'LINE'}])

    assert any(item.rule_id == 'AO-LAYER-001' for item in findings)
    assert any(item.action_id == 'AO-ACTION-LAYER-REVIEW' for item in actions)


def test_hssteel_engine_detects_steel_candidates():
    findings, actions = HSSteelRuleEngine().review_drawing(SYNTHETIC_OBJECTS)

    assert any(item.rule_id == 'HS-MEMBER-001' for item in findings)
    assert any(item.source == 'hssteel' for item in findings)


def test_orchestrator_combines_three_rule_sources():
    orchestrator = DomainRuleOrchestrator(xicad_root='Z:/missing-xicad-for-test')
    review = orchestrator.review_drawing(SYNTHETIC_OBJECTS, task='synthetic review')

    sources = {item.source for item in review.findings}
    assert 'xicad' in sources or review.warnings
    assert 'hssteel' in sources
    assert review.prompt_constraints


def test_prompt_builder_declares_domain_authority_over_com():
    orchestrator = DomainRuleOrchestrator(xicad_root='Z:/missing-xicad-for-test')
    packs = orchestrator.build_knowledge_packs()
    review = orchestrator.review_drawing(SYNTHETIC_OBJECTS, task='prompt test')
    prompt = build_system_drafting_constraints(packs, review)

    assert 'SYSTEM DRAFTING CONSTRAINTS' in prompt
    assert 'XiCAD' in prompt
    assert 'ArchiOffice' in prompt
    assert 'HS-Steel' in prompt
    assert 'ZWCAD COM is only an execution channel' in prompt
