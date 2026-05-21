import json
import subprocess
import sys
from pathlib import Path


def test_stage24_dxf_rewrite_cli(tmp_path: Path):
    source = tmp_path / "a.dxf"
    source.write_text("0\nEOF\n", encoding="utf-8")
    out = tmp_path / "out"
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "src.dxf_style_rewriter.cli",
            "rewrite-dxf",
            "--source-dxf",
            str(source),
            "--out",
            str(out),
        ]
    )
    assert (out / "styled_a.dxf").exists()
    assert (out / "dxf_rewrite_report.json").exists()


def test_stage24_preview_and_merge_cli(tmp_path: Path):
    out = tmp_path / "stage24"
    plan = tmp_path / "plan.json"
    insert = tmp_path / "insert.json"
    styled = tmp_path / "styled.json"
    context = tmp_path / "context.json"
    plan.write_text(json.dumps({"source_dxf": "a.dxf", "insert_layer": "QA-REVIEW"}), encoding="utf-8")
    insert.write_text(json.dumps({"inserted_handle": "H1", "undo_mark_created": True}), encoding="utf-8")
    styled.write_text(json.dumps({"entities": []}), encoding="utf-8")
    context.write_text(json.dumps({"version": "test"}), encoding="utf-8")

    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "src.preview_lifecycle.cli",
            "create-session",
            "--plan",
            str(plan),
            "--insert-result",
            str(insert),
            "--out",
            str(out),
        ]
    )
    assert (out / "preview_session.json").exists()

    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "src.merge_planner.cli",
            "build-merge-candidate",
            "--preview-session",
            str(out / "preview_session.json"),
            "--style-context",
            str(context),
            "--styled-result",
            str(styled),
            "--out",
            str(out),
        ]
    )
    assert (out / "merge_candidate_plan.json").exists()
