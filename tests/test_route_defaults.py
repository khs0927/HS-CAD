from pathlib import Path

from src.orchestrator.route_defaults import build_route_defaults


def test_route_defaults_generates_workspace_and_sample_limit(tmp_path: Path):
    source = tmp_path / 'sample.dwg'
    defaults = build_route_defaults('도면을 분석해줘', source)
    assert defaults.source_root == str(tmp_path)
    assert defaults.sample == 20
    assert defaults.limit == 20
    assert defaults.workspace.startswith('outputs')


def test_route_defaults_keeps_full_run_safe_by_default(tmp_path: Path):
    source = tmp_path / 'sample.dwg'
    defaults = build_route_defaults('전체 도면을 전부 분석해줘', source)
    assert defaults.full_run_requested is True
    assert defaults.sample == 20
    assert defaults.limit == 20
    assert defaults.warnings


def test_route_defaults_accepts_manual_sample_and_limit(tmp_path: Path):
    source = tmp_path / 'sample.dwg'
    defaults = build_route_defaults('전체 도면을 전부 분석해줘', source, sample=100, limit=100)
    assert defaults.sample == 100
    assert defaults.limit == 100
