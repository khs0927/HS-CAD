from pathlib import Path

from src.corpus_run.pipeline_runner import CorpusPipelineRunner
from src.fileizers.dwg_dxf_ezdxf_fileizer import DWGToDXFEzdxfFileizer


def test_dwg_default_fileizer_avoids_full_com_scan(tmp_path: Path) -> None:
    runner = CorpusPipelineRunner(tmp_path / 'workspace')
    assert isinstance(runner.fileizers[0], DWGToDXFEzdxfFileizer)
    assert runner.fileizers[0].engine_name == 'zwcad_saveas_dxf_ezdxf'
