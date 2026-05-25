from __future__ import annotations

import json
from pathlib import Path

from src.analysis.final_todo_integration_readiness import (
    EXPECTED_PHASE_FILES,
    build_final_todo_readiness_report,
    write_final_todo_readiness_outputs,
)


def test_final_todo_readiness_detects_phase_artifacts(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    repo.mkdir()
    workspace.mkdir()

    for name in EXPECTED_PHASE_FILES:
        (workspace / name).write_text(json.dumps({"ok": True}), encoding="utf-8")

    report = build_final_todo_readiness_report(repo_root=repo, workspace=workspace)

    assert report.status == "ready_for_final_review"
    assert all(item.exists for item in report.phase_artifacts)
    assert report.safety["live_execution_ready"] is False


def test_final_todo_readiness_missing_artifacts_is_partial(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    repo.mkdir()
    workspace.mkdir()

    report = build_final_todo_readiness_report(repo_root=repo, workspace=workspace)

    assert report.status == "partial"
    assert any("Not all Phase" in warning for warning in report.warnings)
    assert report.safety["final_runner_implemented"] is False


def test_final_todo_readiness_writes_outputs(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    out_dir = tmp_path / "out"
    repo.mkdir()
    workspace.mkdir()

    result = write_final_todo_readiness_outputs(repo_root=repo, workspace=workspace, out_dir=out_dir)

    assert Path(result["report_json"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["pr_sequence_plan"]).exists()

    payload = json.loads(Path(result["pr_sequence_plan"]).read_text(encoding="utf-8"))
    assert "integration/final-review-pipeline-readiness" in payload["recommended_pr_sequence"]
    assert payload["safety"]["cad_execution_allowed_by_default"] is False
