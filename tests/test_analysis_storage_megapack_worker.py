from pathlib import Path
import pytest
from src.workers.contracts import WorkerInput
from src.workers.analysis_storage_megapack_worker import execute

def test_analysis_storage_megapack_worker_success(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    # Create fake inputs
    in1 = workspace / "in1.json"
    in1.write_text("{}", encoding="utf-8")
    
    worker_input = WorkerInput(
        worker_name="analysis_storage_megapack",
        task="run",
        workspace=str(workspace),
        input_artifacts=[str(in1)],
        options={}
    )
    
    output = execute(worker_input)
    assert output.status == "ok"
    assert len(output.artifacts) == 3
    assert output.warnings == []
    
    for o in ['ANALYSIS_STORAGE_MANIFEST.json', 'ANALYSIS_STORAGE_SUMMARY.md', 'EVIDENCE_GRAPH_STORAGE_EXPORT.json']:
        assert (workspace / o).exists()

def test_analysis_storage_megapack_worker_missing_input(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    worker_input = WorkerInput(
        worker_name="analysis_storage_megapack",
        task="run",
        workspace=str(workspace),
        input_artifacts=["fake.json"],
        options={}
    )
    
    output = execute(worker_input)
    assert output.status == "warning"
    assert "Missing input artifact: fake.json" in output.warnings[0]
