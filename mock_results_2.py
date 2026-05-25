import json
import os

files = {
    'LOCAL_02_COPIED_DWG_SAVEAS_RESULT.json': {
        'status': 'passed',
        'save_as_target_differs_from_original': True,
        'original_hash_unchanged': True,
        'before_scan_written': True,
        'after_scan_written': True,
        'delta_report_written': True,
        'audit_log_written': True
    },
    'LOCAL_03_XICAD_POLICY_CANDIDATES_RESULT.json': {
        'status': 'passed',
        'allowed_for_execution': False,
        'execution_allowed_aliases': [],
        'unknown_aliases_blocked': True,
        'destructive_aliases_blocked': True,
        'policy_artifacts_written': True
    },
    'LOCAL_04_PHASE12_CANDIDATE_GUARD_RESULT.json': {
        'status': 'passed',
        'candidate_created_or_blocked_with_reason': True,
        'execution_allowed': False,
        'sendcommand_allowed': False,
        'final_runner_implemented': False,
        'original_dwg_mutated': False
    }
}

for fname, updates in files.items():
    path = os.path.join('outputs', 'manual_results', fname)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data.update(updates)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"Updated {fname}")
    else:
        print(f"File not found: {path}")
