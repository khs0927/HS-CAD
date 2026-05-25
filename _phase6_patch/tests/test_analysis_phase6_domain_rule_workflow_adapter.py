from __future__ import annotations

import json
from pathlib import Path

from src.analysis.phase6_domain_rule_workflow_adapter import (
    build_phase6_domain_rule_workflow_adapter,
    write_phase6_adapter_outputs,
)


def make_phase5_package(path: Path) -> None:
    payload = {
        "task": "phase5_domain_rule_decision_bridge",
        "status": "partial",
        "findings": [
            {
                "finding_id": "phase5:finding:1",
                "source_decision_id": "phase4:decision-package-readiness",
                "title": "Decision package readiness",
                "status": "ready_for_review",
                "reason": "Artifacts are available.",
                "evidence_refs": ["PHASE4_DECISION_BRIDGE_PACKAGE.json"],
                "blocked_reasons": [],
                "tags": ["phase5"],
            },
            {
                "finding_id": "phase5:finding:2",
                "source_decision_id": "phase4:missing-artifact-review",
                "title": "Missing artifact review",
                "status": "blocked",
                "reason": "Some artifacts are missing.",
                "evidence_refs": ["tables"],
                "blocked_reasons": ["missing_artifacts"],
                "tags": ["phase5"],
            },
        ],
        "action_candidates": [
            {
                "action_id": "phase5:action:1",
                "source_finding_id": "phase5:finding:1",
                "action_type": "domain-rule-review",
                "status": "review_required",
                "command_hint": "domain-rule-decision --review-only",
                "review_required": True,
                "execution_allowed": False,
                "required_evidence": ["PHASE4_DECISION_BRIDGE_PACKAGE.json"],
            }
        ],
        "metrics": [{"key": "coverage_ratio", "value": 0.6}],
        "safety": {"domain_rule_review_only": True, "execution_allowed": False},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_phase6_adapter_normalizes_phase5_package(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    make_phase5_package(workspace / "PHASE5_DOMAIN_RULE_INPUT_PACKAGE.json")

    report = build_phase6_domain_rule_workflow_adapter(workspace)

    assert report.status == "partial"
    assert len(report.normalized_findings) == 2
    assert len(report.review_actions) == 1
    assert report.safety["domain_rule_review_only"] is True
    assert report.safety["execution_allowed"] is False
    assert all(action.execution_allowed is False for action in report.review_actions)


def test_phase6_adapter_missing_phase5_package_is_blocked(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    report = build_phase6_domain_rule_workflow_adapter(workspace)

    assert report.status == "blocked"
    assert report.normalized_findings[0].blocked_reasons == ["missing_phase5_domain_rule_input_package"]
    assert report.safety["command_plan_execution_allowed"] is False


def test_phase6_adapter_writes_outputs(tmp_path: Path):
    workspace = tmp_path / "workspace"
    out_dir = tmp_path / "out"
    workspace.mkdir()
    make_phase5_package(workspace / "PHASE5_DOMAIN_RULE_INPUT_PACKAGE.json")

    result = write_phase6_adapter_outputs(workspace, out_dir=out_dir)

    assert Path(result["report_json"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["domain_rule_decision_input"]).exists()

    payload = json.loads(Path(result["domain_rule_decision_input"]).read_text(encoding="utf-8"))
    assert payload["domain_rule_mode"] == "review_only"
    assert payload["safety"]["xicad_alias_execution_allowed"] is False
