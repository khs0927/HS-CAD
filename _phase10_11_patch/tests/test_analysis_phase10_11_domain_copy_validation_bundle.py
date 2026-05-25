from __future__ import annotations

import json
from pathlib import Path

from src.analysis.phase10_domain_decision_connector import write_phase10_outputs
from src.analysis.phase11_copied_dwg_validation_bridge import write_phase11_outputs
from src.workers.analysis_phase10_11_domain_copy_validation_worker import run


def make_phase8_and_phase9(workspace: Path) -> None:
    phase8 = {
        "task": "phase8_review_gate_chain_bridge",
        "status": "partial",
        "command_plan": {
            "mode": "dry_run_only",
            "dry_run_steps": [
                {
                    "step_id": "phase8:dry-run-step:1",
                    "source_decision_id": "phase7:decision:1",
                    "status": "review_required",
                    "command_type": "domain-rule-review-only",
                    "command_hint": "domain-rule-decision --review-only",
                    "execution_allowed": False,
                    "review_required": True,
                    "blocked_reasons": [],
                }
            ],
            "execution_allowed": False,
        },
        "review_gate": {
            "items": [
                {
                    "gate_id": "phase8:review-gate:1",
                    "source_step_id": "phase8:dry-run-step:1",
                    "status": "needs_human_review",
                    "required_checks": ["execution_allowed_false", "no_sendcommand"],
                }
            ]
        },
        "safety": {"execution_allowed": False},
    }
    phase9 = {
        "task": "phase9_pipeline_readiness_summary",
        "status": "ready_for_review_pipeline",
        "safety": {"ready_for_live_execution": False},
    }
    (workspace / "PHASE8_REVIEW_GATE_CHAIN.json").write_text(json.dumps(phase8), encoding="utf-8")
    (workspace / "PHASE9_PIPELINE_READINESS_SUMMARY.json").write_text(json.dumps(phase9), encoding="utf-8")


def test_phase10_11_bundle_writes_plan_only_artifacts(tmp_path: Path):
    workspace = tmp_path / "workspace"
    out_dir = tmp_path / "out"
    workspace.mkdir()
    make_phase8_and_phase9(workspace)
    original = workspace / "original.dwg"
    original.write_bytes(b"dummy dwg")

    phase10 = write_phase10_outputs(workspace, out_dir=out_dir)
    phase11 = write_phase11_outputs(
        workspace,
        phase10_connector_path=out_dir / "PHASE10_DOMAIN_DECISION_CONNECTOR.json",
        original_dwg=original,
        working_copy_dwg=workspace / "copy.dwg",
        save_as_target=workspace / "result.dwg",
        out_dir=out_dir,
    )

    assert Path(phase10["connector_json"]).exists()
    assert Path(phase11["bridge_json"]).exists()
    assert phase10["safety"]["execution_allowed"] is False
    assert phase11["safety"]["zwcad_com_allowed"] is False


def test_phase10_11_worker_runs_without_cad(tmp_path: Path):
    workspace = tmp_path / "workspace"
    out_dir = tmp_path / "out"
    workspace.mkdir()
    make_phase8_and_phase9(workspace)

    result = run(workspace, out_dir=out_dir)

    assert Path(result["phase10"]["connector_json"]).exists()
    assert Path(result["phase11"]["bridge_json"]).exists()
    assert result["safety"]["sendcommand_allowed"] is False
