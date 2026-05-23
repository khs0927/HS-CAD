from __future__ import annotations

from pathlib import Path

from src.domain_rules.decision_engine import DomainRuleDecisionEngine
from src.domain_rules.decision_report import render_decision_markdown
from src.domain_rules.orchestrator import DomainRuleOrchestrator
from src.workers.domain_rule_decision_worker import load_objects_json, run_domain_rule_decision_worker
from src.reports.json_exporter import export_json


SYNTHETIC_OBJECTS = [
    {'object_name': 'AcDbPolyline', 'entity_type': 'POLYLINE', 'closed': True, 'layer': 'WAL1'},
    {'object_name': 'AcDbBlockReference', 'entity_type': 'INSERT', 'layer': '0', 'name': 'H-300x150'},
    {'object_name': 'AcDbText', 'entity_type': 'TEXT', 'layer': 'ROOM-TEXT', 'text': 'ROOM 101'},
]


def test_decision_engine_returns_review_package():
    engine = DomainRuleDecisionEngine(DomainRuleOrchestrator(xicad_root='Z:/missing-xicad-for-test'))
    package = engine.decide(SYNTHETIC_OBJECTS, task='synthetic decision', source='synthetic')

    assert package.task == 'synthetic decision'
    assert package.status in {'ready_for_review', 'needs_more_evidence', 'blocked'}
    assert package.decisions
    assert package.review_checklist
    assert 'SYSTEM DRAFTING CONSTRAINTS' in package.system_prompt


def test_decision_engine_blocks_empty_objects():
    engine = DomainRuleDecisionEngine(DomainRuleOrchestrator(xicad_root='Z:/missing-xicad-for-test'))
    package = engine.decide([], task='empty decision', source='empty')

    assert package.status == 'blocked'
    assert package.blocked_reasons
    assert package.required_evidence


def test_decision_report_contains_prompt_and_decisions():
    engine = DomainRuleDecisionEngine(DomainRuleOrchestrator(xicad_root='Z:/missing-xicad-for-test'))
    package = engine.decide(SYNTHETIC_OBJECTS, task='report decision', source='synthetic')
    markdown = render_decision_markdown(package)

    assert 'HS-CAD Modification Decision Package' in markdown
    assert 'System drafting constraints' in markdown
    assert 'ZWCAD COM is only an execution channel' in markdown


def test_worker_loads_list_and_dict_shapes(tmp_path: Path):
    list_path = tmp_path / 'objects_list.json'
    dict_path = tmp_path / 'objects_dict.json'
    export_json(SYNTHETIC_OBJECTS, list_path)
    export_json({'objects': SYNTHETIC_OBJECTS}, dict_path)

    assert len(load_objects_json(list_path)) == 3
    assert len(load_objects_json(dict_path)) == 3


def test_worker_writes_decision_artifacts(tmp_path: Path):
    objects_path = tmp_path / 'objects.json'
    out_dir = tmp_path / 'decision'
    export_json(SYNTHETIC_OBJECTS, objects_path)

    result = run_domain_rule_decision_worker(
        objects_path,
        out_dir=out_dir,
        task='worker decision',
        xicad_root='Z:/missing-xicad-for-test',
    )

    assert result['status'] in {'ready_for_review', 'needs_more_evidence', 'blocked'}
    assert Path(result['json']).exists()
    assert Path(result['report']).exists()
    assert Path(result['prompt']).exists()
