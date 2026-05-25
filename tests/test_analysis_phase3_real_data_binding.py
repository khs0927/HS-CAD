from __future__ import annotations
import json
from pathlib import Path
from src.analysis.phase3_real_data_binding import scan_phase1_artifacts, write_phase3_real_data_binding_outputs

def test_phase3_real_data_binding_reads_existing_artifacts(tmp_path: Path):
    workspace = tmp_path / "workspace"; workspace.mkdir()
    (workspace / "TEXT_ROLE_INFERENCE.json").write_text(json.dumps({"items": [{"text": "ROOM", "role": "room_name"}]}), encoding="utf-8")
    (workspace / "GEOMETRY_LOOP_BUILDER.json").write_text(json.dumps([{"id": "loop-1", "area": 123.4}]), encoding="utf-8")
    report = scan_phase1_artifacts(workspace)
    assert report.discovered_count >= 2
    assert report.json_loadable_count >= 2
    assert report.safety["source_mutation_allowed"] is False
    assert report.safety["cad_execution_allowed"] is False

def test_phase3_real_data_binding_writes_reports(tmp_path: Path):
    workspace = tmp_path / "workspace"; out_dir = tmp_path / "out"; workspace.mkdir()
    (workspace / "TABLE_GRID_DETECTOR.json").write_text(json.dumps({"tables": [{"id": "table-1"}]}), encoding="utf-8")
    result = write_phase3_real_data_binding_outputs(workspace, out_dir=out_dir)
    assert Path(result["report_json"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["coverage_json"]).exists()
    payload = json.loads(Path(result["report_json"]).read_text(encoding="utf-8"))
    assert payload["safety"]["derived_artifacts_only"] is True
    assert payload["safety"]["zwcad_com_allowed"] is False

def test_phase3_real_data_binding_missing_workspace_is_warning(tmp_path: Path):
    result = write_phase3_real_data_binding_outputs(tmp_path / "missing", out_dir=tmp_path / "out")
    assert result["status"] == "warning"
    assert result["metrics"]["discovered_artifact_count"] == 0
