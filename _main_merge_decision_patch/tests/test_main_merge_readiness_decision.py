from __future__ import annotations

import json
from pathlib import Path

from src.analysis.main_merge_readiness_decision import (
    build_main_merge_readiness_decision,
    write_main_merge_decision_outputs,
)


def create_required_docs(repo: Path) -> None:
    docs = repo / "docs"
    docs.mkdir(parents=True)
    for name in [
        "90_final_live_runner_deferred_safety_policy.md",
        "91_final_analysis_cli_registration_report.md",
        "92_final_analysis_worker_manifest_registration_report.md",
        "93_final_review_pipeline_readiness_report.md",
        "95_main_readiness_local_validation_report.md",
        "97_post_pr53_main_merge_local_validation_report.md",
        "98_local_only_zwcad_xicad_validation_runbook.md",
    ]:
        (docs / name).write_text("# ok\n", encoding="utf-8")


def create_post_pr53_plan(workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "ready_for_human_main_readiness_review",
        "gate_checks": [
            {"id": "gate:required-final-reports", "status": "ok"},
            {"id": "gate:pr53-artifacts", "status": "ok"},
        ],
        "final_live_runner_gate": {"can_implement_now": False},
        "local_only_validation_steps": [
            {"id": "local-01", "title": "Copied DWG validation", "status": "local_only_pending"}
        ],
        "safety": {
            "source_mutation_allowed": False,
            "original_dwg_mutation_allowed": False,
            "cad_execution_allowed_by_default": False,
            "zwcad_com_allowed_by_default": False,
            "sendcommand_allowed_by_default": False,
            "xicad_alias_execution_allowed_by_default": False,
            "final_live_runner_implemented": False,
        },
    }
    (workspace / "POST_PR53_MAIN_MERGE_LOCAL_VALIDATION_PLAN.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def test_main_merge_decision_ready_when_gates_clear(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    repo.mkdir()
    create_required_docs(repo)
    create_post_pr53_plan(workspace)

    package = build_main_merge_readiness_decision(repo_root=repo, post_pr53_workspace=workspace)

    assert package["status"] == "ready_for_human_main_merge_review"
    assert package["safety"]["final_live_runner_implemented"] is False
    assert "final live runner" in " ".join(package["main_merge_disallowed_scope"]).lower()


def test_main_merge_decision_blocks_missing_docs(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    repo.mkdir()
    create_post_pr53_plan(workspace)

    package = build_main_merge_readiness_decision(repo_root=repo, post_pr53_workspace=workspace)

    assert package["status"] == "blocked"
    assert any(gate["status"] == "blocked" for gate in package["gates"])
    assert package["safety"]["sendcommand_allowed_by_default"] is False


def test_main_merge_decision_writes_outputs(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    out = tmp_path / "out"
    repo.mkdir()
    create_post_pr53_plan(workspace)

    result = write_main_merge_decision_outputs(repo_root=repo, post_pr53_workspace=workspace, out_dir=out)

    assert Path(result["decision_json"]).exists()
    assert Path(result["decision_md"]).exists()
    assert Path(result["main_merge_pr_body_draft"]).exists()
    assert Path(result["post_merge_local_validation_prompt"]).exists()
