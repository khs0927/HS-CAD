from __future__ import annotations

import sys
from pathlib import Path

from src.analysis.cli_shortcut_plan import build_cli_shortcut_plan
from src.analysis.evidence_join_fusion import fuse_join_evidence
from src.analysis.report_packager import build_report_package_manifest
from src.analysis.validation_rule_engine import run_validation_rules
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'analysis_evidence_megapack'
BACKEND = 'analysis_evidence_megapack'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='analysis_evidence_megapack_v0',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    artifacts: list[str] = []
    warnings: list[str] = []
    metrics = {}
    try:
        evidence = fuse_join_evidence(workspace)
        rules = run_validation_rules(workspace)
        package = build_report_package_manifest(workspace)
        shortcuts = build_cli_shortcut_plan(workspace)
        artifacts.extend([
            str(workspace / 'EVIDENCE_JOIN_FUSION.json'),
            str(workspace / 'EVIDENCE_JOIN_FUSION.md'),
            str(workspace / 'VALIDATION_RULE_RESULTS.json'),
            str(workspace / 'VALIDATION_RULE_RESULTS.md'),
            str(workspace / 'REPORT_PACKAGE_MANIFEST.json'),
            str(workspace / 'REPORT_PACKAGE_MANIFEST.md'),
            str(workspace / 'CLI_SHORTCUT_PLAN.json'),
            str(workspace / 'CLI_SHORTCUT_PLAN.md'),
        ])
        metrics.update({
            'evidence_node_count': (evidence.get('summary') or {}).get('node_count', 0),
            'evidence_edge_count': (evidence.get('summary') or {}).get('edge_count', 0),
            'validation_overall_status': (rules.get('summary') or {}).get('overall_status'),
            'validation_error_count': (rules.get('summary') or {}).get('error_count', 0),
            'validation_warning_count': (rules.get('summary') or {}).get('warning_count', 0),
            'report_package_file_count': (package.get('summary') or {}).get('file_count', 0),
            'cli_shortcut_count': (shortcuts.get('summary') or {}).get('shortcut_count', 0),
        })
        warnings.extend(evidence.get('warnings') or [])
        warnings.extend(rules.get('warnings') or [])
        warnings.extend(package.get('warnings') or [])
        warnings.extend(shortcuts.get('warnings') or [])
    except Exception as exc:
        return WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message=str(exc), provenance=provenance)

    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status='warning',
        artifacts=artifacts,
        signals=[
            {
                'id': 'analysis_evidence_megapack',
                'score': 0.65,
                'evidence': ['evidence fusion, validation rules, report package manifest, and cli shortcut plan generated'],
            }
        ],
        warnings=warnings,
        metrics=metrics,
        provenance=provenance,
    )


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        output = WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message='missing WorkerInput path argument')
        print(output.to_json())
        return 2
    worker_input = WorkerInput.from_json_file(args[0])
    output = run_worker(worker_input)
    print(output.to_json())
    return 0 if output.status in {'ok', 'warning', 'unavailable'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
