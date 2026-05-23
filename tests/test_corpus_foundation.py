from __future__ import annotations

import json
from pathlib import Path

import ezdxf

from src.corpus.evidence import EvidencePackageBuilder
from src.corpus.indexer import CorpusIndexer
from src.corpus.learner import CorpusLearner
from src.corpus.quality import CorpusQualityAuditor
from src.corpus.query import CorpusQuery
from src.corpus.report_builder import CorpusReportBuilder
from src.corpus.validator import FileizedRecordValidator
from src.corpus_run.manifest import scan_manifest, write_manifest
from src.corpus_run.pipeline_runner import CorpusPipelineRunner
from src.fileizers.dxf_ezdxf_fileizer import DXFEzdxfFileizer
from src.fileizers.image_fileizer import ImageMetadataFileizer
from src.fileizers.pdf_pymupdf_fileizer import PDFPyMuPDFFileizer


def _make_sample_dxf(path: Path) -> None:
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (1000, 0), dxfattribs={'layer': 'WAL1'})
    msp.add_text('T100 glasswool panel', dxfattribs={'layer': 'TEXT'})
    doc.saveas(path)


def _make_sample_pdf(path: Path) -> None:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text((24, 80), 'PDF T180 roof panel')
    doc.save(path)


def _make_sample_image(path: Path) -> None:
    from PIL import Image

    img = Image.new('RGB', (120, 80), 'white')
    img.save(path)


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


def test_pdf_fileizer_extracts_text(tmp_path: Path) -> None:
    pdf = tmp_path / 'sample.pdf'
    _make_sample_pdf(pdf)
    record = PDFPyMuPDFFileizer().fileize(pdf, file_id='pdf', relative_path='sample.pdf')
    assert record.status == 'ok'
    assert record.engine == 'pymupdf'
    assert any('T180' in row['text'] for row in record.texts)


def test_image_fileizer_records_metadata(tmp_path: Path) -> None:
    image = tmp_path / 'sample.png'
    _make_sample_image(image)
    record = ImageMetadataFileizer().fileize(image, file_id='image', relative_path='sample.png')
    assert record.status == 'ok'
    assert record.metadata['width'] == 120
    assert record.metadata['height'] == 80


def test_index_query_report_from_record(tmp_path: Path) -> None:
    dxf = tmp_path / 'sample.dxf'
    _make_sample_dxf(dxf)
    record = DXFEzdxfFileizer().fileize(dxf, file_id='sample', relative_path='sample.dxf')
    sqlite_path = tmp_path / 'cad_knowledge.sqlite'
    CorpusIndexer(sqlite_path).index_record(record)
    result = CorpusQuery(sqlite_path).search_text('glasswool')
    assert result['matches']
    evidence = EvidencePackageBuilder(sqlite_path).build('glasswool')
    assert evidence['evidence'][0]['evidence_type'] == 'text'
    summary = CorpusLearner(sqlite_path).build_summary()
    assert summary['status'] == 'ok'
    report = CorpusReportBuilder(sqlite_path).build_markdown()
    assert 'HS-CAD Corpus Report' in report


def test_pipeline_prepare_fileize_index_learn_report(tmp_path: Path) -> None:
    source = tmp_path / 'source'
    source.mkdir()
    _make_sample_dxf(source / 'sample.dxf')
    _make_sample_pdf(source / 'sample.pdf')
    _make_sample_image(source / 'sample.png')
    workspace = tmp_path / 'workspace'
    runner = CorpusPipelineRunner(workspace)
    prepared = runner.prepare(source)
    assert prepared['file_count'] == 3
    fileized = runner.fileize()
    assert fileized['ok'] == 3
    validation = FileizedRecordValidator().validate_json_dir(workspace / 'fileized' / 'json')
    assert validation['invalid_count'] == 0
    indexed = runner.index()
    assert indexed['indexed'] == 3
    learned = runner.learn()
    assert Path(learned['learning_summary']).exists()
    queried = runner.query('glasswool')
    assert queried['matches']
    evidence = runner.evidence('T180')
    assert evidence['evidence']
    quality_md = CorpusQualityAuditor(workspace).write_markdown()
    assert Path(quality_md).exists()
    reported = runner.report()
    assert Path(reported['report']).exists()
