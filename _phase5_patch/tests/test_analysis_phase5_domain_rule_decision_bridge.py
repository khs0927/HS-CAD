from __future__ import annotations

import json
from pathlib import Path

from src.analysis.phase5_domain_rule_decision_bridge import (
    build_phase5_domain_decision_bridge,
    write_phase5_bridge_outputs,
)


def make_phase4_package(path: Path) -> None:
    payload = {
        "task": "phase4_metrics_decision_bridge",
        "status": "partial",
        "metrics": [{"key": "coverage_ratio", "value": 0.6, "source": "phase3"}],
        "decision_candidates": [
            {
                "decision_id": "phase4:decision-package-readiness",
                "title": "Decision package readiness",
                "status": "ready_for_review",
                "reason": "Real analysis artifacts were discovered.",
                "required_evidence": ["PHASE3_REAL_DATA_BINDING_REPORT.json"],
                "blocked_reasons": [],
            },
            {
                "decision_id": "phase4:missing-artifact-review",
                "title": "Missing artifact review",
                "status": "review_required",
                "reason": "Some artifacts are missing.",
                "required_evidence": ["tables"],
                "blocked_reasons": ["missing_artifacts"],
            },
        ],
        "safety": {
            "source_mutation_allowed": False,
            "cad_execution_allowed": False,
            "derived_artifacts_only": True,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_phase5_bridge_maps_phase4_candidates_to_domain_findings(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    make_phase4_package(workspace / "PHASE4_DECISION_BRIDGE_PACKAGE.json")

    report = build_phase5_domain_decision_bridge(workspace)

    assert report.status == "partial"
    assert len(report.findings) == 2
    assert len(report.action_candidates) == 1
    assert report.safety["domain_rule_review_only"] is True
    assert report.safety["execution_allowed"] is False


def test_phase5_bridge_missing_phase4_package_is_blocked(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    report = build_phase5_domain_decision_bridge(workspace)

    assert report.status == "blocked"
    assert report.findings[0].blocked_reasons == ["missing_phase4_decision_bridge_package"]
    assert report.safety["sendcommand_allowed"] is False


def test_phase5_bridge_writes_outputs(tmp_path: Path):
    workspace = tmp_path / "workspace"
    out_dir = tmp_path / "out"
    workspace.mkdir()
    make_phase4_package(workspace / "PHASE4_DECISION_BRIDGE_PACKAGE.json")

    result = write_phase5_bridge_outputs(workspace, out_dir=out_dir)

    assert Path(result["report_json"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["domain_rule_input_package"]).exists()

    payload = json.loads(Path(result["domain_rule_input_package"]).read_text(encoding="utf-8"))
    assert payload["safety"]["domain_rule_review_only"] is True
    assert payload["safety"]["xicad_alias_execution_allowed"] is False
