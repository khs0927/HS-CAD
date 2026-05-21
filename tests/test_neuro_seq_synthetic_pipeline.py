from pathlib import Path

import pytest

from neuro_seq_cad.app.cli import write_analysis_outputs
from neuro_seq_cad.review.synthetic_floorplan_generator import make_synthetic_floorplan


def test_synthetic_pipeline_exports_expected_files(tmp_path: Path):
    pytest.importorskip("ezdxf")
    image = make_synthetic_floorplan(tmp_path / "sample_plan.png")
    out = tmp_path / "demo"
    write_analysis_outputs(image, out, export_dxf=True)

    assert (out / "result_centerline.dxf").exists()
    assert (out / "result_wallsolid.dxf").exists()
    assert (out / "result.json").exists()
    assert (out / "qa_report.md").exists()
    assert (out / "overlay.png").exists()

