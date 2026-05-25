from __future__ import annotations

import json
from pathlib import Path

from src.analysis.pr55_59_combined_review import (
    PR_STACK,
    build_pr55_59_combined_review,
    write_outputs,
)


def test_pr_stack_contains_55_to_59():
    prs = [item["pr"] for item in PR_STACK]
    assert prs == ["#55", "#56", "#57", "#58", "#59"]


def test_combined_review_is_safe_by_default(tmp_path: Path):
    package = build_pr55_59_combined_review(repo_root=tmp_path)

    assert package["status"] == "ready_for_human_main_merge_review"
    assert package["decision"]["can_auto_merge"] is False
    assert package["decision"]["can_start_final_live_runner"] is False
    assert package["safety"]["cad_execution_allowed"] is False
    assert package["safety"]["final_live_runner_implemented"] is False


def test_combined_review_preserves_disallowed_scope(tmp_path: Path):
    package = build_pr55_59_combined_review(repo_root=tmp_path)
    text = " ".join(package["disallowed_scope"]).lower()

    assert "sendcommand" in text
    assert "final live runner" in text
    assert "original dwg mutation" in text


def test_combined_review_writes_outputs(tmp_path: Path):
    result = write_outputs(repo_root=tmp_path, out_dir=tmp_path / "out")

    assert Path(result["package_json"]).exists()
    assert Path(result["package_md"]).exists()
    assert Path(result["operator_prompt"]).exists()
    assert Path(result["post_merge_json"]).exists()

    payload = json.loads(Path(result["package_json"]).read_text(encoding="utf-8"))
    assert payload["decision"]["main_merge_requires_human_decision"] is True
