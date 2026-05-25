from __future__ import annotations

import json
from pathlib import Path

from src.analysis.post_main_local_validation_live_runner_safety import (
    build_post_main_local_validation_live_runner_safety_bundle,
    write_post_main_bundle_outputs,
)


def test_post_main_bundle_keeps_execution_disabled(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    repo.mkdir()
    workspace.mkdir()

    package = build_post_main_local_validation_live_runner_safety_bundle(
        repo_root=repo,
        operator_review_workspace=workspace,
    )

    assert package["safety"]["final_live_runner_implemented"] is False
    assert package["safety"]["zwcad_com_sendcommand_allowed"] is False
    assert package["safety"]["post_main_local_validation_manual_only"] is True
    assert len(package["post_main_local_validation_commands"]) == 4


def test_final_live_runner_requirements_are_fail_closed(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    repo.mkdir()
    workspace.mkdir()

    package = build_post_main_local_validation_live_runner_safety_bundle(repo, operator_review_workspace=workspace)
    requirement_text = " ".join(req["requirement"].lower() for req in package["final_live_runner_safety_requirements"])

    assert "refuse original" in requirement_text
    assert "fail closed" in requirement_text or "refuse execution" in requirement_text
    assert any(risk["severity"] == "critical" for risk in package["risk_register"])


def test_post_main_bundle_writes_outputs(tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    out = tmp_path / "out"
    repo.mkdir()
    workspace.mkdir()
    (workspace / "MAIN_MERGE_OPERATOR_REVIEW_PACKAGE.json").write_text(
        json.dumps({"status": "ready_for_operator_main_merge_review"}),
        encoding="utf-8",
    )

    result = write_post_main_bundle_outputs(
        repo_root=repo,
        operator_review_workspace=workspace,
        out_dir=out,
    )

    assert Path(result["package_json"]).exists()
    assert Path(result["local_validation_json"]).exists()
    assert Path(result["final_live_runner_spec_json"]).exists()
    assert Path(result["safety_spec_prompt"]).exists()
    assert result["safety"]["final_live_runner_requires_separate_safety_spec_pr"] is True
