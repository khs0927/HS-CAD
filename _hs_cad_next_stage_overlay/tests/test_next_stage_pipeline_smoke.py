from __future__ import annotations

import json
from pathlib import Path

from hscad.pipelines.next_stage_pipeline import run_next_stage_pipeline


def test_next_stage_pipeline_smoke(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/minimal_floorplan.dxf")
    result = run_next_stage_pipeline(fixture, tmp_path)
    assert result["safety_flags"]["cad_execution_allowed_by_default"] is False
    assert (tmp_path / "NEXT_STAGE_PIPELINE_RESULT.json").exists()
    assert (tmp_path / "FUSION_MATRIX.json").exists()
    assert (tmp_path / "CROSS_VALIDATION.json").exists()
    assert (tmp_path / "result_centerline.dxf").exists()
    assert (tmp_path / "result_wallsolid.dxf").exists()
    assert (tmp_path / "qa_overlay.dxf").exists()
    payload = json.loads((tmp_path / "NEXT_STAGE_PIPELINE_RESULT.json").read_text(encoding="utf-8"))
    assert payload["drawing"]["entities"]
    assert payload["domain_rule_results"]
