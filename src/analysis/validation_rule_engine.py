from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.entity_loader import read_json, write_json_and_md

DEFAULT_RULES = [
    {'id': 'required_batch_summary', 'artifact': 'BATCH_VALIDATION_SUMMARY.json', 'severity': 'error'},
    {'id': 'required_text_roles', 'artifact': 'TEXT_ROLE_INFERENCE.json', 'severity': 'warning'},
    {'id': 'required_geometry', 'artifact': 'REAL_GEOMETRY_POLYGONIZER.json', 'severity': 'warning'},
    {'id': 'required_spatial_join', 'artifact': 'STRTREE_SPATIAL_JOIN.json', 'severity': 'warning'},
    {'id': 'required_evidence_fusion', 'artifact': 'EVIDENCE_JOIN_FUSION.json', 'severity': 'warning'},
]


def run_validation_rules(workspace: str | Path, *, max_warning_count: int = 50) -> dict[str, Any]:
    base = Path(workspace)
    findings: list[dict[str, Any]] = []
    for rule in DEFAULT_RULES:
        path = base / str(rule['artifact'])
        if not path.exists():
            findings.append({
                'rule_id': rule['id'],
                'severity': rule['severity'],
                'status': 'fail',
                'message': f"missing artifact: {rule['artifact']}",
                'artifact': rule['artifact'],
            })
        else:
            payload = read_json(path)
            warnings = payload.get('warnings') or []
            if len(warnings) > max_warning_count:
                findings.append({
                    'rule_id': f"{rule['id']}_warning_count",
                    'severity': 'warning',
                    'status': 'fail',
                    'message': f"warning count {len(warnings)} exceeds {max_warning_count}",
                    'artifact': rule['artifact'],
                })
            else:
                findings.append({
                    'rule_id': rule['id'],
                    'severity': 'info',
                    'status': 'pass',
                    'message': 'artifact present',
                    'artifact': rule['artifact'],
                })
    findings.extend(_metric_rules(base))
    error_count = sum(1 for f in findings if f.get('severity') == 'error' and f.get('status') == 'fail')
    warning_count = sum(1 for f in findings if f.get('severity') == 'warning' and f.get('status') == 'fail')
    payload = {
        'backend': 'validation_rule_engine',
        'schema_version': '0.1',
        'summary': {
            'rule_count': len(findings),
            'error_count': error_count,
            'warning_count': warning_count,
            'overall_status': 'fail' if error_count else ('warning' if warning_count else 'pass'),
        },
        'findings': findings,
        'todo': [
            'Add configurable validation_rules.json.',
            'Add thresholds based on real webhard baseline.',
            'Add per-discipline rules for architectural/structural/electrical drawings.',
            'Add CI exit code mapping after rules stabilize.',
        ],
        'warnings': [f.get('message') for f in findings if f.get('status') == 'fail'],
    }
    return write_json_and_md(base, 'VALIDATION_RULE_RESULTS', payload, _markdown(payload))


def _metric_rules(base: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    evidence = read_json(base / 'EVIDENCE_JOIN_FUSION.json')
    summary = evidence.get('summary') or {}
    if evidence:
        if int(summary.get('node_count') or 0) == 0:
            findings.append({'rule_id': 'evidence_has_nodes', 'severity': 'warning', 'status': 'fail', 'message': 'evidence graph has no nodes', 'artifact': 'EVIDENCE_JOIN_FUSION.json'})
        if int(summary.get('edge_count') or 0) == 0:
            findings.append({'rule_id': 'evidence_has_edges', 'severity': 'warning', 'status': 'fail', 'message': 'evidence graph has no edges', 'artifact': 'EVIDENCE_JOIN_FUSION.json'})
    dashboard = read_json(base / 'QUALITY_DASHBOARD_MANIFEST.json')
    dsum = dashboard.get('summary') or {}
    if dashboard and int(dsum.get('missing_section_count') or 0) > 0:
        findings.append({'rule_id': 'dashboard_sections_ready', 'severity': 'warning', 'status': 'fail', 'message': 'dashboard has missing sections', 'artifact': 'QUALITY_DASHBOARD_MANIFEST.json'})
    return findings


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    lines = [
        '# Validation Rule Results',
        '',
        f"- Overall status: `{s.get('overall_status')}`",
        f"- Rule count: `{s.get('rule_count')}`",
        f"- Errors: `{s.get('error_count')}`",
        f"- Warnings: `{s.get('warning_count')}`",
        '',
        '| Rule | Severity | Status | Message |',
        '|---|---|---|---|',
    ]
    for row in payload.get('findings') or []:
        lines.append(f"| {row.get('rule_id')} | {row.get('severity')} | {row.get('status')} | {row.get('message')} |")
    lines.append('')
    return '\n'.join(lines)
