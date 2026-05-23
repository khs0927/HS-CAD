from __future__ import annotations

from pathlib import Path

from src.domain_rules.review_gate_builder import build_review_gate_package
from src.domain_rules.review_gate_report import render_review_gate_markdown
from src.workers.domain_rule_review_gate_worker import load_command_plan, run_domain_rule_review_gate_worker
from src.reports.json_exporter import export_json


SAFE_COMMAND_PLAN = {
    'task': 'safe command plan',
    'source_decision_package': 'synthetic',
    'status': 'ready_for_human_review',
    'dry_run_steps': [
        {
            'order': 1,
            'step_id': 'dry-run-1',
            'title': 'Prepare XiCAD layer mapping review',
            'risk': 'mutation_gated',
            'command_type': 'xicad-safe-plan',
            'command_hint': 'xicad-safe-plan --alias LAYER-MAP',
            'source_decision_id': 'action:xicad:XI-ACTION-LAYER-MAP',
            'reason': 'Layer mapping requires review.',
            'preconditions': ['Original DWG must not be mutated.'],
            'expected_outputs': ['dry-run action list'],
            'blocked_reason': '',
        }
    ],
    'review_table': [{'order': 1, 'title': 'Prepare XiCAD layer mapping review', 'risk': 'mutation_gated'}],
    'execution_queue_candidate': {
        'queue_id': 'domain-rule-execution-candidate',
        'status': 'awaiting_approval',
        'steps': [],
        'approval_required': True,
        'save_as_required': True,
        'notes': ['not execution'],
    },
    'blocked_reasons': [],
    'warnings': [],
}


def test_review_gate_allows_dry_run_only_for_safe_plan():
    package = build_review_gate_package(SAFE_COMMAND_PLAN, source='safe-plan')

    assert package.status == 'ready_for_dry_run_only'
    assert not package.blocked_reasons
    assert all(check.status == 'pass' for check in package.checks)
    assert 'Run dry-run only' in package.allowed_next_steps


def test_review_gate_blocks_unsafe_queue():
    plan = dict(SAFE_COMMAND_PLAN)
    plan['execution_queue_candidate'] = dict(SAFE_COMMAND_PLAN['execution_queue_candidate'])
    plan['execution_queue_candidate']['approval_required'] = False
    plan['execution_queue_candidate']['save_as_required'] = False
    package = build_review_gate_package(plan, source='unsafe-plan')

    assert package.status == 'blocked'
    assert any(check.status == 'fail' for check in package.checks)


def test_review_gate_report_contains_signoff_and_safety_note():
    package = build_review_gate_package(SAFE_COMMAND_PLAN, source='safe-plan')
    markdown = render_review_gate_markdown(package)

    assert 'HS-CAD Domain Rule Review Gate' in markdown
    assert 'Required sign-off' in markdown
    assert 'Safety note' in markdown
    assert 'Original DWG files must not be modified' in markdown


def test_review_gate_worker_writes_artifacts(tmp_path: Path):
    plan_path = tmp_path / 'DOMAIN_RULE_COMMAND_PLAN.json'
    out_dir = tmp_path / 'gate'
    export_json(SAFE_COMMAND_PLAN, plan_path)

    loaded = load_command_plan(plan_path)
    assert loaded['task'] == 'safe command plan'

    result = run_domain_rule_review_gate_worker(plan_path, out_dir=out_dir)

    assert result['status'] == 'ready_for_dry_run_only'
    assert Path(result['gate_json']).exists()
    assert Path(result['gate_report']).exists()
    assert Path(result['signoff_manifest']).exists()
