from __future__ import annotations

import json
from pathlib import Path

from src.analysis.post_merge_local_validation_execution_pack import (
    LOCAL_VALIDATION_STEPS,
    PR61_CONTEXT,
    build_post_merge_local_validation_execution_pack,
    write_post_merge_local_validation_execution_outputs,
)


def test_pr61_context_preserved():
    assert PR61_CONTEXT["pr_url"] == "https://github.com/khs0927/HS-CAD/pull/61"
    assert PR61_CONTEXT["reported_validation"]["full_pytest"] == "235 passed, 16 skipped"
    assert PR61_CONTEXT["final_live_runner_decision"]["implementation_pr_can_start"] is False


def test_pack_blocks_when_paths_overlap():
    pack = build_post_merge_local_validation_execution_pack(
        original_dwg="C:/same.dwg",
        working_copy_dwg="C:/same.dwg",
        save_as_target="C:/same.dwg",
    )

    assert pack["status"] == "blocked"
    assert any(gate["status"] == "blocked" for gate in pack["gates"])
    assert pack["safety"]["this_package_runs_cad"] is False


def test_pack_renders_four_manual_steps():
    pack = build_post_merge_local_validation_execution_pack()

    assert pack["status"] == "ready_for_manual_local_validation"
    assert len(pack["local_validation_steps"]) == 4
    assert all("rendered_command" in step for step in pack["local_validation_steps"])
    assert pack["final_live_runner_state"]["implementation_allowed"] is False


def test_outputs_are_written(tmp_path: Path):
    result = write_post_merge_local_validation_execution_outputs(
        out_dir=tmp_path / "pack",
        result_template_dir=tmp_path / "results",
    )

    assert Path(result["pack_json"]).exists()
    assert Path(result["pack_md"]).exists()
    assert Path(result["command_template_ps1"]).exists()
    assert Path(result["result_schema_json"]).exists()
    assert len(result["result_templates"]) == len(LOCAL_VALIDATION_STEPS)

    payload = json.loads(Path(result["pack_json"]).read_text(encoding="utf-8"))
    assert payload["safety"]["this_package_implements_final_live_runner"] is False
