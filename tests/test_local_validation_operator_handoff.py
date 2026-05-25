from __future__ import annotations

import json
from pathlib import Path

from src.analysis.local_validation_operator_handoff import (
    PR62_CONTEXT,
    build_local_validation_operator_handoff,
    write_operator_handoff_outputs,
)


def test_pr62_context_preserved():
    assert PR62_CONTEXT["pr_url"] == "https://github.com/khs0927/HS-CAD/pull/62"
    assert PR62_CONTEXT["final_live_runner_gate"]["final_live_runner_implementation_allowed"] is False


def test_handoff_ready_when_paths_are_distinct():
    package = build_local_validation_operator_handoff(
        original_dwg="C:/cad/original.dwg",
        working_copy_dwg="C:/cad/copy.dwg",
        save_as_target="C:/cad/result.dwg",
    )

    assert package["status"] == "ready_for_manual_operator_validation"
    assert package["safety"]["this_package_runs_cad"] is False
    assert package["final_live_runner_decision"]["implementation_allowed"] is False


def test_handoff_blocks_when_paths_overlap():
    package = build_local_validation_operator_handoff(
        original_dwg="C:/cad/same.dwg",
        working_copy_dwg="C:/cad/same.dwg",
        save_as_target="C:/cad/same.dwg",
    )

    assert package["status"] == "blocked"
    assert any(gate["status"] == "blocked" for gate in package["gates"])


def test_handoff_writes_outputs(tmp_path: Path):
    result = write_operator_handoff_outputs(
        out_dir=tmp_path / "handoff",
        original_dwg="C:/cad/original.dwg",
        working_copy_dwg="C:/cad/copy.dwg",
        save_as_target="C:/cad/result.dwg",
    )

    assert Path(result["package_json"]).exists()
    assert Path(result["package_md"]).exists()
    assert Path(result["operator_prompt"]).exists()
    assert Path(result["result_finalization"]).exists()

    payload = json.loads(Path(result["package_json"]).read_text(encoding="utf-8"))
    assert payload["safety"]["this_package_runs_powershell"] is False
