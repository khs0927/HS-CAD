from __future__ import annotations

import json
from pathlib import Path

from src.analysis.phase12_manual_live_execution_candidate import (
    build_phase12_manual_live_execution_candidate,
    write_phase12_outputs,
)


def make_inputs(workspace: Path) -> tuple[Path, Path, Path]:
    original = workspace / "original.dwg"
    copy = workspace / "working_copy.dwg"
    save_target = workspace / "result.dwg"
    original.write_bytes(b"dummy dwg")
    copy.write_bytes(b"dummy dwg")

    phase11 = {
        "original_dwg": str(original),
        "working_copy_dwg": str(copy),
        "save_as_target": str(save_target),
        "execution_allowed": False,
    }
    allowlist = {
        "dry_run_allowed_aliases": ["WAL"],
        "blocked_aliases": ["ERASE"],
        "execution_allowed_aliases": [],
    }
    (workspace / "PHASE11_COPY_VALIDATION_CLI_PLAN.json").write_text(json.dumps(phase11), encoding="utf-8")
    (workspace / "XICAD_ALIAS_ALLOWLIST_PLAN.json").write_text(json.dumps(allowlist), encoding="utf-8")
    return original, copy, save_target


def test_phase12_blocks_by_default(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    make_inputs(workspace)

    package = build_phase12_manual_live_execution_candidate(workspace, alias="WAL")

    assert package["status"] == "blocked"
    assert "manual_live_flag_not_enabled" in package["candidate"]["blocked_reasons"]
    assert "operator_not_approved" in package["candidate"]["blocked_reasons"]
    assert package["candidate"]["execution_allowed"] is False
    assert package["candidate"]["sendcommand_allowed"] is False


def test_phase12_manual_ready_candidate_still_does_not_execute(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    make_inputs(workspace)

    package = build_phase12_manual_live_execution_candidate(
        workspace,
        alias="WAL",
        manual_live_flag=True,
        operator_approved=True,
    )

    assert package["status"] == "manual_ready_candidate"
    assert package["candidate"]["execution_allowed"] is False
    assert package["candidate"]["sendcommand_allowed"] is False
    assert package["safety"]["manual_live_candidate"] is True


def test_phase12_blocks_unknown_or_blocked_alias(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    make_inputs(workspace)

    unknown = build_phase12_manual_live_execution_candidate(
        workspace,
        alias="UNKNOWN_ABC",
        manual_live_flag=True,
        operator_approved=True,
    )
    blocked = build_phase12_manual_live_execution_candidate(
        workspace,
        alias="ERASE",
        manual_live_flag=True,
        operator_approved=True,
    )

    assert "alias_not_in_dry_run_allowlist" in unknown["candidate"]["blocked_reasons"]
    assert "alias_is_blocked_by_allowlist" in blocked["candidate"]["blocked_reasons"]


def test_phase12_writes_outputs(tmp_path: Path):
    workspace = tmp_path / "workspace"
    out_dir = tmp_path / "out"
    workspace.mkdir()
    make_inputs(workspace)

    result = write_phase12_outputs(
        workspace,
        alias="WAL",
        manual_live_flag=True,
        operator_approved=True,
        out_dir=out_dir,
    )

    assert Path(result["candidate_json"]).exists()
    assert Path(result["candidate_md"]).exists()
    assert Path(result["final_runner_guard"]).exists()
    assert result["safety"]["sendcommand_allowed_by_default"] is False
