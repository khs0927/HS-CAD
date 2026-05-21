from pathlib import Path

import pytest

from src.drawing_fileizers.dxf_fileizer import DXFFileizer


def test_dxf_fileizer_reads_basic_dxf(tmp_path: Path):
    ezdxf = pytest.importorskip("ezdxf")

    dxf_path = tmp_path / "sample.dxf"
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (1000, 0), dxfattribs={"layer": "WAL1"})
    msp.add_text("글라스울패널 100T", dxfattribs={"layer": "TEXT"})
    doc.saveas(dxf_path)

    record = DXFFileizer().fileize(dxf_path, tmp_path / "out")
    assert record.status == "success"
    assert len(record.entities) >= 2
    assert any("글라스울" in t.text for t in record.texts)
