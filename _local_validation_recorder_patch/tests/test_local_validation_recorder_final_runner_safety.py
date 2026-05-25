from __future__ import annotations

import json
from pathlib import Path

from src.analysis.local_validation_recorder_final_runner_safety import (
    LOCAL_VALIDATION_EXPECTED_RESULTS,
    PR59_CONTEXT,
    build_empty_local_validation_result_templates,
    build_local_validation_summary,
    write_local_validation_recorder_outputs,
)


def test_pr59_context_is_preserved():
    assert PR59_CONTEXT["pr_url"] == "https://github.com/khs0927/HS-CAD/pull/59"
    assert PR59_CONTEXT["reported_validation"]["full_pytest"] == "227 passed, 16 skipped"


def test_recorder_creates_templates_and_blocks_by_default(tmp_path: Path):
    result_dir = tmp_path / "results"
    templates = build_empty_local_validation_result_templates(result_dir)

    assert len(templates) == len(LOCAL_VALIDATION_EXPECTED_RESULTS)

    summary = build_local_validation_summary(result_dir)
    assert summary["status"] == "not_ready"
    assert summary["final_live_runner_implementation_allowed"] is False
    assert summary["safety"]["this_bundle_executes_cad"] is False


def test_recorder_passes_when_all_manual_results_match(tmp_path: Path):
    result_dir = tmp_path / "results"
    result_dir.mkdir()

    for spec in LOCAL_VALIDATION_EXPECTED_RESULTS:
        payload = {"id": spec["id"], "title": spec["title"]}
        for field_name in spec["required_fields"]:
            payload[field_name] = None
        for key, value in spec["pass_conditions"].items():
            payload[key] = value
        (result_dir / spec["required_result_file"]).write_text(json.dumps(payload), encoding="utf-8")

    summary = build_local_validation_summary(result_dir)
    assert summary["status"] == "passed"
    assert summary["all_local_validations_passed"] is True
    assert summary["final_live_runner_spec_ready"] is True
    assert summary["final_live_runner_implementation_allowed"] is False


def test_recorder_writes_outputs(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    result = write_local_validation_recorder_outputs(
        repo_root=repo,
        result_dir=tmp_path / "results",
        out_dir=tmp_path / "out",
        create_templates=True,
    )

    assert Path(result["summary_json"]).exists()
    assert Path(result["summary_md"]).exists()
    assert Path(result["final_gate_json"]).exists()
    assert Path(result["pr59_context_json"]).exists()
