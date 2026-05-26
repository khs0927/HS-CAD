from __future__ import annotations

from pathlib import Path

from src.domain_rules.command_plan_builder import build_command_plan
from src.domain_rules.command_plan_report import render_command_plan_markdown
from src.workers.domain_rule_command_plan_worker import load_decision_package, run_domain_rule_command_plan_worker
from src.reports.json_exporter import export_json


SYNTHETIC_DECISION_PACKAGE = {
    'task': 'synthetic modification decision',
    'source': 'synthetic',
    'status': 'ready_for_review',
    'decisions': [
        {
            'decision_id': 'action:xicad:XI-ACTION-LAYER-MAP',
            'title': 'Prepare XiCAD layer mapping review',
            'status': 'ready_for_review',
            'priority': 'medium',
            'reason': 'XiCAD rule-based modification requires verified layer mappings.',
            'rule_sources': ['xicad'],
            'evidence_refs': [],
            'next_steps': ['Create dry-run plan'],
            'command_hints': ['xicad-safe-plan --alias LAYER-MAP'],
            'warnings': [],
            'metadata': {'risk': 'review_required', 'save_as_required': True},
        },
        {
            'decision_id': 'decision:manual-review',
            'title': 'Manual review required',
            'status': 'ready_for_review',
            'priority': 'low',
            'reason': 'No direct command hint is available.',
            'rule_sources': ['combined'],
            'evidence_refs': [],
            'next_steps': ['Review manually'],
            'command_hints': [],
            'warnings': [],
            'metadata': {},
        },
    ],
    'blocked_reasons': [],
    'required_evidence': [],
    'review_checklist': ['Run dry-run before execution'],
    'system_prompt': 'SYSTEM DRAFTING CONSTRAINTS\nZWCAD COM is only an execution channel.\n',
    'warnings': [],
}


def test_build_command_plan_maps_command_hints_to_dry_run_steps():
    plan = build_command_plan(SYNTHETIC_DECISION_PACKAGE, source='synthetic-package')

    assert plan.status == 'ready_for_human_review'
    assert len(plan.dry_run_steps) == 2
    assert any(step.command_type == 'xicad-safe-plan' for step in plan.dry_run_steps)
    assert plan.execution_queue_candidate.approval_required is True
    assert plan.execution_queue_candidate.save_as_required is True
    assert len(plan.execution_queue_candidate.steps) == 1


def test_build_command_plan_blocks_when_decision_package_is_blocked():
    payload = dict(SYNTHETIC_DECISION_PACKAGE)
    payload['blocked_reasons'] = ['No analyzed drawing objects were provided.']
    plan = build_command_plan(payload, source='blocked-package')

    assert plan.status == 'blocked'
    assert plan.blocked_reasons == ['No analyzed drawing objects were provided.']
    assert any(step.risk == 'blocked' for step in plan.dry_run_steps)


def test_command_plan_report_contains_safety_sections():
    plan = build_command_plan(SYNTHETIC_DECISION_PACKAGE, source='synthetic-package')
    markdown = render_command_plan_markdown(plan)

    assert 'HS-CAD Domain Rule Command Plan' in markdown
    assert 'Safety posture' in markdown
    assert 'Dry-run steps' in markdown
    assert 'Execution queue candidate' in markdown
    assert 'Original DWG must not be mutated' in markdown


def test_worker_loads_and_writes_command_plan_artifacts(tmp_path: Path):
    package_path = tmp_path / 'DOMAIN_RULE_DECISION_PACKAGE.json'
    out_dir = tmp_path / 'command_plan'
    export_json(SYNTHETIC_DECISION_PACKAGE, package_path)

    loaded = load_decision_package(package_path)
    assert loaded['task'] == 'synthetic modification decision'

    result = run_domain_rule_command_plan_worker(package_path, out_dir=out_dir)

    assert result['status'] == 'ready_for_human_review'
    assert Path(result['plan_json']).exists()
    assert Path(result['report']).exists()
    assert Path(result['review_table']).exists()
    assert Path(result['execution_queue_candidate']).exists()
