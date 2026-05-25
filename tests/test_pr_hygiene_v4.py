from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_script(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_commit_candidate_filter_excludes_runtime_and_cad_files() -> None:
    module = _load_script(Path("scripts/list_hscad_pr_commit_candidates.py"))
    assert module.is_excluded("outputs/main_code_smoke/FINAL_REPORT.md")
    assert module.is_excluded("_incoming/main_code_overlay_v4/APPLY_INSTRUCTIONS.md")
    assert module.is_excluded("tests/fixtures/runtime_sample.dxf")
    assert module.is_excluded("bundle.zip")
    assert not module.is_excluded("src/hscad/app/review_cli_registry.py")
    assert not module.is_excluded("docs/34_main_code_overlay_v4_pr_readiness_report.md")


def test_cleaner_collects_known_runtime_dirs(tmp_path: Path) -> None:
    module = _load_script(Path("scripts/clean_hscad_runtime_artifacts.py"))
    (tmp_path / "outputs").mkdir()
    (tmp_path / "_incoming").mkdir()
    (tmp_path / "pkg" / "__pycache__").mkdir(parents=True)
    targets = {p.name for p in module.collect_targets(tmp_path)}
    assert "outputs" in targets
    assert "_incoming" in targets
    assert "__pycache__" in targets
