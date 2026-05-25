from __future__ import annotations

import json
from pathlib import Path

from src.analysis.final_live_runner_safety_spec_gate import (
    REQUIRED_SAFETY_DOCS,
    build_final_live_runner_safety_spec_gate,
    write_final_live_runner_safety_spec_gate_outputs,
)


def write_required_docs(repo: Path) -> None:
    docs = repo / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    for rel in REQUIRED_SAFETY_DOCS:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("# ok\n", encoding="utf-8")


def test_safety_spec_gate_blocks_without_local_summary(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write_required_docs(repo)

    package = build_final_live_runner_safety_spec_gate(repo_root=repo, local_validation_summary_json=tmp_path / "missing.json")

    assert package["status"] == "blocked"
    assert package["approval_decision"]["implementation_pr_can_start"] is False
    assert package["safety"]["final_live_runner_implementation_allowed"] is False


def test_safety_spec_gate_ready_when_summary_passed_and_docs_exist(tmp_path: Path):
    repo = tmp_path / "repo"
    summary_path = tmp_path / "summary.json"
    repo.mkdir()
    write_required_docs(repo)
    summary_path.write_text(
        json.dumps({"status": "passed", "all_local_validations_passed": True}),
        encoding="utf-8",
    )

    package = build_final_live_runner_safety_spec_gate(repo_root=repo, local_validation_summary_json=summary_path)

    assert package["status"] == "ready_for_safety_spec_review"
    assert package["approval_decision"]["safety_spec_pr_can_be_reviewed"] is True
    assert package["approval_decision"]["implementation_pr_can_start"] is False


def test_safety_spec_gate_blocks_missing_docs(tmp_path: Path):
    repo = tmp_path / "repo"
    summary_path = tmp_path / "summary.json"
    repo.mkdir()
    summary_path.write_text(
        json.dumps({"status": "passed", "all_local_validations_passed": True}),
        encoding="utf-8",
    )

    package = build_final_live_runner_safety_spec_gate(repo_root=repo, local_validation_summary_json=summary_path)

    assert package["status"] == "blocked"
    assert any(gate["id"] == "gate:safety-spec-docs" and gate["status"] == "blocked" for gate in package["gates"])


def test_safety_spec_gate_writes_outputs(tmp_path: Path):
    repo = tmp_path / "repo"
    summary_path = tmp_path / "summary.json"
    out = tmp_path / "out"
    repo.mkdir()
    write_required_docs(repo)
    summary_path.write_text(
        json.dumps({"status": "passed", "all_local_validations_passed": True}),
        encoding="utf-8",
    )

    result = write_final_live_runner_safety_spec_gate_outputs(
        repo_root=repo,
        local_validation_summary_json=summary_path,
        out_dir=out,
    )

    assert Path(result["package_json"]).exists()
    assert Path(result["package_md"]).exists()
    assert Path(result["constraints_json"]).exists()
    assert Path(result["test_matrix_json"]).exists()
    assert result["safety"]["this_package_implements_runner"] is False
