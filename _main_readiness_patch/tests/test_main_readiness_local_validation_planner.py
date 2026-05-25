from __future__ import annotations

import json
from pathlib import Path

from src.analysis.main_readiness_local_validation_planner import (
    EXPECTED_FINAL_REVIEW_ARTIFACTS,
    build_main_readiness_plan,
    write_main_readiness_plan_outputs,
)


def test_main_readiness_plan_detects_ready_workspace(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    repo.mkdir()
    workspace.mkdir()
    (repo / "docs").mkdir()
    (repo / "config").mkdir()
    (repo / "src").mkdir()

    required_docs = [
        "91_final_analysis_cli_registration_report.md",
        "92_final_analysis_worker_manifest_registration_report.md",
        "93_final_review_pipeline_readiness_report.md",
        "90_final_live_runner_deferred_safety_policy.md",
    ]
    for name in required_docs:
        (repo / "docs" / name).write_text("# ok\n", encoding="utf-8")
    (repo / "src" / "main.py").write_text("# main\n", encoding="utf-8")
    (repo / "config" / "worker_manifest.json").write_text("[]", encoding="utf-8")

    for name in EXPECTED_FINAL_REVIEW_ARTIFACTS:
        (workspace / name).write_text(json.dumps({"ok": True}), encoding="utf-8")

    plan = build_main_readiness_plan(repo_root=repo, final_review_workspace=workspace)

    assert plan["status"] == "ready_for_main_readiness_review"
    assert plan["safety"]["final_live_runner_implemented"] is False
    assert plan["safety"]["local_only_validation_required_before_live_runner"] is True


def test_main_readiness_plan_blocks_missing_docs(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    repo.mkdir()
    workspace.mkdir()

    plan = build_main_readiness_plan(repo_root=repo, final_review_workspace=workspace)

    assert plan["status"] == "blocked"
    assert any(check["status"] == "blocked" for check in plan["checks"])
    assert plan["safety"]["sendcommand_allowed_by_default"] is False


def test_main_readiness_plan_writes_outputs(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    out = tmp_path / "out"
    repo.mkdir()
    workspace.mkdir()

    result = write_main_readiness_plan_outputs(repo_root=repo, final_review_workspace=workspace, out_dir=out)

    assert Path(result["plan_json"]).exists()
    assert Path(result["plan_md"]).exists()
    assert Path(result["local_todo_json"]).exists()

    payload = json.loads(Path(result["plan_json"]).read_text(encoding="utf-8"))
    assert payload["safety"]["cad_execution_allowed_by_default"] is False
