from __future__ import annotations

import json
from pathlib import Path

from src.analysis.phase7_domain_decision_package_bridge import write_phase7_outputs
from src.analysis.phase8_review_gate_chain_bridge import write_phase8_outputs
from src.analysis.phase9_pipeline_readiness_summary import write_phase9_outputs
from src.workers.analysis_phase7_9_review_pipeline_bundle_worker import run


def make_phase6_input(path: Path) -> None:
    payload = {
        "task": "phase6_domain_rule_workflow_adapter",
        "status": "partial",
        "findings": [
            {
                "id": "phase6:finding:1",
                "source": "phase5:finding:1",
                "title": "Ready review finding",
                "status": "ready_for_review",
                "reason": "ready",
                "evidence_refs": ["PHASE5_DOMAIN_RULE_INPUT_PACKAGE.json"],
                "blocked_reasons": [],
                "tags": ["phase6"],
            },
            {
                "id": "phase6:finding:2",
                "source": "phase5:finding:2",
                "title": "Blocked finding",
                "status": "blocked",
                "reason": "blocked",
                "evidence_refs": [],
                "blocked_reasons": ["missing_artifacts"],
                "tags": ["phase6"],
            },
        ],
        "review_actions": [
            {
                "id": "phase6:action:1",
                "source_finding_id": "phase6:finding:1",
                "command_hint": "domain-rule-decision --review-only",
                "execution_allowed": False,
                "required_evidence": ["PHASE5_DOMAIN_RULE_INPUT_PACKAGE.json"],
            }
        ],
        "safety": {"execution_allowed": False},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_phase7_8_9_bundle_writes_review_only_artifacts(tmp_path: Path):
    workspace = tmp_path / "workspace"
    out_dir = tmp_path / "out"
    workspace.mkdir()
    make_phase6_input(workspace / "DOMAIN_RULE_DECISION_INPUT_FROM_PHASE6.json")

    phase7 = write_phase7_outputs(workspace, out_dir=out_dir)
    phase8 = write_phase8_outputs(workspace, phase7_package_path=out_dir / "PHASE7_DOMAIN_DECISION_PACKAGE.json", out_dir=out_dir)
    phase9 = write_phase9_outputs(out_dir, out_dir=out_dir)

    assert Path(phase7["package_json"]).exists()
    assert Path(phase8["artifacts"]["PHASE8_REVIEW_GATE_CHAIN.json"]).exists()
    assert Path(phase9["summary_json"]).exists()
    assert phase8["safety"]["execution_allowed"] is False
    assert phase9["safety"]["ready_for_live_execution"] is False


def test_phase7_9_bundle_worker_runs(tmp_path: Path):
    workspace = tmp_path / "workspace"
    out_dir = tmp_path / "out"
    workspace.mkdir()
    make_phase6_input(workspace / "DOMAIN_RULE_DECISION_INPUT_FROM_PHASE6.json")

    result = run(workspace, out_dir=out_dir)

    assert Path(result["phase7"]["package_json"]).exists()
    assert Path(result["phase9"]["summary_json"]).exists()
    assert result["safety"]["cad_execution_allowed"] is False
