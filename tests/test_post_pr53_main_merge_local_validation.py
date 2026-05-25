from __future__ import annotations

import json
from pathlib import Path

from src.analysis.post_pr53_main_merge_local_validation import (
    build_post_pr53_main_merge_plan,
    write_post_pr53_outputs,
)


def create_required_repo_docs(repo: Path) -> None:
    docs = repo / "docs"
    docs.mkdir(parents=True)
    for name in [
        "91_final_analysis_cli_registration_report.md",
        "92_final_analysis_worker_manifest_registration_report.md",
        "93_final_review_pipeline_readiness_report.md",
        "95_main_readiness_local_validation_report.md",
        "90_final_live_runner_deferred_safety_policy.md",
    ]:
        (docs / name).write_text("# ok\n", encoding="utf-8")


def create_pr53_outputs(workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "MAIN_READINESS_LOCAL_VALIDATION_PLAN.json").write_text(json.dumps({"status": "ready"}), encoding="utf-8")
    (workspace / "LOCAL_ONLY_VALIDATION_TODO.json").write_text(json.dumps([{"id": "local"}]), encoding="utf-8")


def test_post_pr53_plan_ready_when_required_docs_and_artifacts_exist(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    repo.mkdir()
    create_required_repo_docs(repo)
    create_pr53_outputs(workspace)

    plan = build_post_pr53_main_merge_plan(repo_root=repo, main_readiness_workspace=workspace)

    assert plan["status"] == "ready_for_human_main_readiness_review"
    assert plan["safety"]["final_live_runner_implemented"] is False
    assert plan["final_live_runner_gate"]["can_implement_now"] is False


def test_post_pr53_plan_blocks_missing_required_docs(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    repo.mkdir()
    create_pr53_outputs(workspace)

    plan = build_post_pr53_main_merge_plan(repo_root=repo, main_readiness_workspace=workspace)

    assert plan["status"] == "blocked"
    assert any(check["status"] == "blocked" for check in plan["gate_checks"])
    assert plan["safety"]["sendcommand_allowed_by_default"] is False


def test_post_pr53_writes_outputs(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    out = tmp_path / "out"
    repo.mkdir()
    create_pr53_outputs(workspace)

    result = write_post_pr53_outputs(repo_root=repo, main_readiness_workspace=workspace, out_dir=out)

    assert Path(result["plan_json"]).exists()
    assert Path(result["plan_md"]).exists()
    assert Path(result["local_steps_json"]).exists()
    assert Path(result["merge_checklist_json"]).exists()

    payload = json.loads(Path(result["plan_json"]).read_text(encoding="utf-8"))
    assert payload["pr53_context"]["pr_url"] == "https://github.com/khs0927/HS-CAD/pull/53"
