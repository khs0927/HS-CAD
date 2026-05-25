from __future__ import annotations

import json
from pathlib import Path

from src.analysis.main_merge_operator_review import (
    PR56_CONTEXT,
    build_main_merge_operator_review,
    write_main_merge_operator_review_outputs,
)


def test_pr56_context_preserved():
    assert PR56_CONTEXT["pr_url"] == "https://github.com/khs0927/HS-CAD/pull/56"
    assert PR56_CONTEXT["reported_decision"] == "main-ready yes"


def test_operator_review_is_safe_by_default(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    repo.mkdir()
    workspace.mkdir()

    package = build_main_merge_operator_review(repo_root=repo, pr56_workspace=workspace)

    assert package["safety"]["auto_merge_allowed"] is False
    assert package["safety"]["final_live_runner_implemented"] is False
    assert package["safety"]["zwcad_com_sendcommand_allowed"] is False
    assert "final live runner" in " ".join(package["main_merge_disallowed_scope"]).lower()


def test_operator_review_writes_outputs(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    out = tmp_path / "out"
    repo.mkdir()
    workspace.mkdir()
    (workspace / "PR55_MAIN_READY_REVIEW_ONLY_VALIDATION.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    (workspace / "PR55_MAIN_READY_CHECKLIST.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    result = write_main_merge_operator_review_outputs(repo_root=repo, pr56_workspace=workspace, out_dir=out)

    assert Path(result["package_json"]).exists()
    assert Path(result["package_md"]).exists()
    assert Path(result["main_merge_operator_prompt"]).exists()
    assert Path(result["post_merge_local_validation_prompt"]).exists()
    assert result["safety"]["operator_review_required"] is True
