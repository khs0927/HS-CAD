import json
from pathlib import Path

from src.dxf_style_rewriter.rewriter import rewrite_dxf


def test_rewrite_dxf_missing_source(tmp_path: Path):
    report = rewrite_dxf(tmp_path / "missing.dxf", None, None, tmp_path)
    assert report.source_exists is False
    assert report.output_dxf is None
    assert report.errors


def test_rewrite_dxf_copies_source_and_reports_actions(tmp_path: Path):
    source = tmp_path / "result_wallsolid.dxf"
    source.write_text("0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n", encoding="utf-8")
    styled = tmp_path / "styled.json"
    styled.write_text(
        json.dumps({"entities": [{"original_entity": {"id": "w1", "entity_type": "wall"}, "target_layer": "A-WALL"}]}),
        encoding="utf-8",
    )
    report = rewrite_dxf(source, styled, None, tmp_path / "out")
    assert Path(report.output_dxf).exists()
    assert report.copied_without_rewrite is True
    assert report.actions
