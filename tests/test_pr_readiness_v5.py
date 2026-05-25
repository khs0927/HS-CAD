from __future__ import annotations

import importlib.util
from pathlib import Path

def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_validate_hscad_pr_ready_blocks_runtime_paths() -> None:
    module = load_module(Path("scripts/validate_hscad_pr_ready.py"), "validate_hscad_pr_ready")
    blocked, reason = module.is_forbidden("outputs/main_code_smoke/FUSION_MATRIX.json")
    assert blocked
    assert "runtime prefix" in reason

    blocked, reason = module.is_forbidden("tests/fixtures/minimal_floorplan.dxf")
    assert blocked
    assert "DXF" in reason

def test_validate_hscad_pr_ready_allows_expected_source_paths() -> None:
    module = load_module(Path("scripts/validate_hscad_pr_ready.py"), "validate_hscad_pr_ready")
    assert module.is_expected("src/hscad/pipelines/main_code_pipeline.py")
    assert module.is_expected("tests/test_pr_readiness_v5.py")
    assert module.is_expected("docs/35_main_code_overlay_pr_body.md")
    assert not module.is_expected("random.tmp")

def test_generate_pr_body_mentions_review_only_safety() -> None:
    module = load_module(Path("scripts/generate_hscad_pr_body.py"), "generate_hscad_pr_body")
    body = module.render(Path("."), "Test PR")
    assert "review-only" in body.lower()
    assert "No CAD live execution" in body
    assert "ZWCAD COM" in body
