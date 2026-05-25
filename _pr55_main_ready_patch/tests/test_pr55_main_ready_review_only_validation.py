from __future__ import annotations

import json
from pathlib import Path

from src.analysis.pr55_main_ready_review_only_validator import (
    PR55_CONTEXT,
    build_pr55_main_ready_validation_report,
    write_pr55_validation_outputs,
)


def test_pr55_context_is_preserved():
    assert PR55_CONTEXT["pr_url"] == "https://github.com/khs0927/HS-CAD/pull/55"
    assert PR55_CONTEXT["decision_status"] == "ready_for_human_main_merge_review"


def test_pr55_validation_report_is_review_only(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("# main\n", encoding="utf-8")

    report = build_pr55_main_ready_validation_report(repo_root=repo)

    assert report["safety"]["actual_main_merge_performed"] is False
    assert report["safety"]["final_live_runner_implemented"] is False
    assert report["safety"]["zwcad_com_sendcommand_allowed"] is False
    assert "final live runner" in " ".join(report["disallowed_scope"]).lower()


def test_pr55_validation_writes_outputs(tmp_path: Path):
    repo = tmp_path / "repo"
    out = tmp_path / "out"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("# main\n", encoding="utf-8")

    result = write_pr55_validation_outputs(repo_root=repo, out_dir=out)

    assert Path(result["report_json"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["checklist_json"]).exists()

    payload = json.loads(Path(result["checklist_json"]).read_text(encoding="utf-8"))
    assert payload["safety"]["main_direct_push_allowed"] is False
