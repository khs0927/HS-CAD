from __future__ import annotations

import json
from pathlib import Path

from src.analysis.local_evidence_finalization_safety_spec_approval import (
    build_local_evidence_finalization_safety_spec_approval,
    write_local_evidence_finalization_outputs,
)


def write_required_outputs(repo: Path, *, ready: bool = True) -> None:
    (repo / "outputs/local_validation_evidence_review").mkdir(parents=True, exist_ok=True)
    (repo / "outputs/local_validation_recorder").mkdir(parents=True, exist_ok=True)
    (repo / "outputs/final_live_runner_safety_spec_gate").mkdir(parents=True, exist_ok=True)

    (repo / "outputs/local_validation_evidence_review/LOCAL_VALIDATION_EVIDENCE_REVIEW.json").write_text(
        json.dumps({"status": "ready_for_safety_spec_review" if ready else "blocked"}),
        encoding="utf-8",
    )
    (repo / "outputs/local_validation_recorder/LOCAL_VALIDATION_RESULT_SUMMARY.json").write_text(
        json.dumps({"status": "passed" if ready else "not_ready", "all_local_validations_passed": ready}),
        encoding="utf-8",
    )
    (repo / "outputs/final_live_runner_safety_spec_gate/FINAL_LIVE_RUNNER_SAFETY_SPEC_GATE.json").write_text(
        json.dumps({"status": "ready_for_safety_spec_review" if ready else "blocked"}),
        encoding="utf-8",
    )


def test_finalization_blocks_when_evidence_missing(tmp_path: Path):
    package = build_local_evidence_finalization_safety_spec_approval(repo_root=tmp_path)
    assert package["status"] == "blocked"
    assert package["decision"]["implementation_pr_can_start"] is False
    assert package["safety"]["this_package_runs_cad"] is False


def test_finalization_ready_when_all_evidence_ready(tmp_path: Path):
    write_required_outputs(tmp_path, ready=True)
    package = build_local_evidence_finalization_safety_spec_approval(repo_root=tmp_path)
    assert package["status"] == "ready_for_human_safety_spec_approval"
    assert package["decision"]["safety_spec_human_approval_can_start"] is True
    assert package["decision"]["implementation_pr_can_start"] is False


def test_finalization_blocks_when_evidence_not_ready(tmp_path: Path):
    write_required_outputs(tmp_path, ready=False)
    package = build_local_evidence_finalization_safety_spec_approval(repo_root=tmp_path)
    assert package["status"] == "blocked"
    assert package["counts"]["blocked"] >= 1


def test_finalization_writes_outputs(tmp_path: Path):
    write_required_outputs(tmp_path, ready=True)
    result = write_local_evidence_finalization_outputs(repo_root=tmp_path, out_dir=tmp_path / "out")
    assert Path(result["package_json"]).exists()
    assert Path(result["package_md"]).exists()
    assert Path(result["human_prompt"]).exists()
    assert Path(result["hard_gates_json"]).exists()
