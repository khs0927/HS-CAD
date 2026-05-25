from __future__ import annotations

from scripts.list_hscad_commit_candidates import is_excluded


def test_commit_candidate_filter_excludes_runtime_artifacts() -> None:
    assert is_excluded("outputs/main_code_smoke/FUSION_MATRIX.json")
    assert is_excluded("_incoming/main_code_overlay_v3/APPLY_INSTRUCTIONS.md")
    assert is_excluded("foo/__pycache__/bar.pyc")
    assert is_excluded("tests/fixtures/runtime.dxf")
    assert not is_excluded("src/hscad/pipelines/evidence_bridge_pipeline.py")
    assert not is_excluded("tests/test_evidence_bridge_pipeline_smoke.py")
