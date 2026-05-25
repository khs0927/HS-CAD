from __future__ import annotations

import json
from pathlib import Path

from src.analysis.human_main_merge_review_gate import (
    build_human_main_merge_review_gate,
    write_human_main_merge_review_outputs,
)


def test_human_main_merge_gate_is_safe_by_default(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    repo.mkdir()
    workspace.mkdir()

    package = build_human_main_merge_review_gate(repo_root=repo, post_main_safety_workspace=workspace)

    assert package["safety"]["auto_merge_allowed"] is False
    assert package["safety"]["this_package_merges_main"] is False
    assert package["safety"]["final_live_runner_implemented"] is False
    assert package["safety"]["zwcad_com_sendcommand_allowed"] is False
    assert package["status"] == "ready_for_human_main_merge_review"


def test_human_main_merge_gate_includes_pr58_context(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    repo.mkdir()
    workspace.mkdir()

    package = build_human_main_merge_review_gate(repo_root=repo, post_main_safety_workspace=workspace)
    urls = " ".join(item["url"] for item in package["pr_stack_context"])

    assert "https://github.com/khs0927/HS-CAD/pull/58" in urls
    assert any("final live runner" in item.lower() for item in package["main_merge_disallowed_scope"])


def test_human_main_merge_gate_writes_outputs(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    out = tmp_path / "out"
    repo.mkdir()
    workspace.mkdir()
    (workspace / "POST_MAIN_LOCAL_VALIDATION_LIVE_RUNNER_SAFETY_BUNDLE.json").write_text(
        json.dumps({"status": "ok"}),
        encoding="utf-8",
    )

    result = write_human_main_merge_review_outputs(repo_root=repo, post_main_safety_workspace=workspace, out_dir=out)

    assert Path(result["package_json"]).exists()
    assert Path(result["package_md"]).exists()
    assert Path(result["operator_prompt"]).exists()
    assert Path(result["post_merge_prompt"]).exists()
    assert Path(result["final_live_runner_guard"]).exists()
