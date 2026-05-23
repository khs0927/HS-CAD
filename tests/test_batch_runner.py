from pathlib import Path

import ezdxf

from src.corpus_run.batch_runner import CorpusBatchRunner
from src.corpus_run.pipeline_runner import CorpusPipelineRunner


def _make_sample_dxf(path: Path, text: str) -> None:
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_text(text, dxfattribs={'layer': 'TEXT'})
    doc.saveas(path)


def test_batch_runner_processes_in_offsets_and_skips_existing(tmp_path: Path):
    source = tmp_path / 'source'
    source.mkdir()
    for index in range(3):
        _make_sample_dxf(source / f'sample_{index}.dxf', f'text {index}')
    workspace = tmp_path / 'workspace'
    CorpusPipelineRunner(workspace).prepare(source, sample=3)

    first = CorpusBatchRunner(workspace).run_batches(batch_size=2, max_batches=1, finalize=False)
    assert first['next_offset'] == 2
    assert first['batches'][0]['result']['ok'] == 2

    second = CorpusBatchRunner(workspace).run_batches(batch_size=2, max_batches=1, start_offset=0, skip_existing=True, finalize=True)
    assert second['batches'][0]['result']['skipped'] == 2
    assert (workspace / 'BATCH_RUN.json').exists()
    assert (workspace / 'RUN_SUMMARY.md').exists()
