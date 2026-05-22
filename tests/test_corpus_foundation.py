from __future__ import annotations

import json
from pathlib import Path

import ezdxf

from src.corpus.indexer import CorpusIndexer
from src.corpus.query import CorpusQuery
from src.corpus.report_builder import CorpusReportBuilder
from src.corpus_run.manifest import scan_manifest, write_manifest
from src.corpus_run.pipeline_runner import CorpusPipelineRunner
from src.fileizers.dxf_ezdxf_fileizer import DXFEzdxfFileizer


def _make_sample_dxf(path: Path) -> None:
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (1000, 0), dxfattribs={'layer': 'WAL1'})
    msp.add_text('T100 glasswool panel', dxfattribs={'layer': 'TEXT'})
    doc.saveas(path)


def test_manifest_scan_and_write(tmp_path: Path) -> None:
    source = tmp_path / 'source'
    source.mkdir()
    dxf = source / 'sample.dxf'
    _make_sample_dxf(dxf)
    entries = scan_manifest(source)
    assert len(entries) == 1
    assert entries[0].extension == '.dxf'
    manifest = tmp_path / 'workspace' / 'run_manifest.json'
    write_manifest(entries, manifest)
    payload = json.loads(manifest.read_text(encoding='utf-8'))
    assert payload['file_count'] == 1


def test_dxf_fileizer_returns_stable_record(tmp_path: Path) -> None:
    dxf = tmp_path / 'sample.dxf'
    _make_sample_dxf(dxf)
    record = DXFEzdxfFileizer().fileize(dxf, file_id='sample', relative_path='sample.dxf')
    assert record.status == 'ok'
    assert record.engine == 'ezdxf'
    assert record.layers
    assert any('glasswool' in row['text'] for row in record.texts)


def test_index_query_report_from_record(tmp_path: Path) -> None:
    dxf = tmp_path / 'sample.dxf'
    _make_sample_dxf(dxf)
    record = DXFEzdxfFileizer().fileize(dxf, file_id='sample', relative_path='sample.dxf')
    sqlite_path = tmp_path / 'cad_knowledge.sqlite'
    CorpusIndexer(sqlite_path).index_record(record)
    result = CorpusQuery(sqlite_path).search_text('glasswool')
    assert result['matches']
    report = CorpusReportBuilder(sqlite_path).build_markdown()
    assert 'HS-CAD Corpus Report' in report


def test_pipeline_prepare_fileize_index_report(tmp_path: Path) -> None:
    source = tmp_path / 'source'
    source.mkdir()
    _make_sample_dxf(source / 'sample.dxf')
    workspace = tmp_path / 'workspace'
    runner = CorpusPipelineRunner(workspace)
    prepared = runner.prepare(source)
    assert prepared['file_count'] == 1
    fileized = runner.fileize()
    assert fileized['ok'] == 1
    indexed = runner.index()
    assert indexed['indexed'] == 1
    queried = runner.query('glasswool')
    assert queried['matches']
    reported = runner.report()
    assert Path(reported['report']).exists()
