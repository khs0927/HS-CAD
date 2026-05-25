from __future__ import annotations

import json
from pathlib import Path

from hscad.pipelines.main_code_pipeline import run_main_code_pipeline
from tests.fixtures.minimal_floorplan_factory import write_minimal_floorplan_dxf


def test_main_code_pipeline_uses_generated_fixture(tmp_path: Path) -> None:
    fixture = write_minimal_floorplan_dxf(tmp_path / "generated" / "minimal_floorplan.dxf")
    out = tmp_path / "pipeline"
    result = run_main_code_pipeline(fixture, out)
    assert result["safety_flags"]["cad_execution_allowed_by_default"] is False
    assert (out / "FUSION_MATRIX.json").exists()
    assert (out / "CROSS_VALIDATION.json").exists()
    assert (out / "DOMAIN_RULE_RESULTS.json").exists()
    assert (out / "FINAL_REPORT.md").exists()
    assert (out / "result_centerline.dxf").exists()
    assert (out / "result_wallsolid.dxf").exists()
    assert (out / "qa_overlay.dxf").exists()
    matrix = json.loads((out / "FUSION_MATRIX.json").read_text(encoding="utf-8"))
    assert matrix["evidence_count"] >= 1
