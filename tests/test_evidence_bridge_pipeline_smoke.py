from __future__ import annotations

from pathlib import Path

from hscad.pipelines.evidence_bridge_pipeline import run_evidence_bridge_pipeline
from tests.fixtures.legacy_artifact_factory import write_legacy_artifact_set


def test_evidence_bridge_pipeline_outputs(tmp_path: Path) -> None:
    legacy = write_legacy_artifact_set(tmp_path / "legacy_outputs")
    out = tmp_path / "bridge_out"
    result = run_evidence_bridge_pipeline(legacy, out)
    assert result["bridge"]["artifact_count"] >= 5
    assert result["fusion"]["evidence_count"] >= 8
    assert (out / "LEGACY_ARTIFACT_BRIDGE_RESULT.json").exists()
    assert (out / "EVIDENCE_GRAPH.json").exists()
    assert (out / "FUSION_MATRIX.json").exists()
    assert (out / "CROSS_VALIDATION.json").exists()
    assert (out / "EVIDENCE_BRIDGE_REPORT.md").exists()
    assert (out / "hscad_evidence_bridge.sqlite3").exists()
    assert result["sqlite_counts"]["evidence"] >= 8
