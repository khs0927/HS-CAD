from __future__ import annotations

from pathlib import Path

from hscad.core.jsonio import read_json
from hscad.pipelines.main_code_pipeline import run_main_code_pipeline
from tests.fixtures.minimal_floorplan_factory import write_minimal_floorplan_dxf


def test_main_code_pipeline_smoke(tmp_path: Path):
    fixture = write_minimal_floorplan_dxf(tmp_path / "minimal_floorplan.dxf")
    out = tmp_path / "main_code"
    result = run_main_code_pipeline(fixture, out)
    assert Path(result["fusion_outputs"]["fusion_matrix"]).exists()
    assert Path(result["dxf_review_outputs"]["qa_overlay"]).exists()
    assert Path(result["sqlite_index"]).exists()
    assert Path(result["final_report"]).exists()
    payload = read_json(out / "MAIN_CODE_PIPELINE_RESULT.json")
    assert payload["sqlite_counts"]["drawings"] == 1
    assert payload["safety_flags"]["cad_execution_allowed_by_default"] is False
