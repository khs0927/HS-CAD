import json
from pathlib import Path

from src.corpus_run.result_summarizer import CorpusRunResultSummarizer


def test_run_result_summarizer_builds_checklist(tmp_path: Path):
    workspace = tmp_path / 'workspace'
    (workspace / 'fileized' / 'json').mkdir(parents=True)
    (workspace / 'failures').mkdir()
    (workspace / 'tmp' / 'dxf' / 'abc').mkdir(parents=True)
    (workspace / 'tmp' / 'dxf' / 'abc' / 'abc.dwg').write_text('stub', encoding='utf-8')
    (workspace / 'tmp' / 'dxf' / 'abc' / 'abc.dxf').write_text('stub', encoding='utf-8')
    (workspace / 'QUALITY_AUDIT.md').write_text('# QA', encoding='utf-8')
    (workspace / 'FINAL_REPORT.md').write_text('# Report', encoding='utf-8')
    (workspace / 'webhard_sample_run.json').write_text(json.dumps({
        'stages': [
            {'stage': 'prepare', 'status': 'ok'},
            {'stage': 'fileize', 'status': 'ok'},
            {'stage': 'validate', 'status': 'ok'},
            {'stage': 'index', 'status': 'ok'},
            {'stage': 'learn', 'status': 'ok'},
            {'stage': 'quality', 'status': 'ok'},
            {'stage': 'report', 'status': 'ok'},
        ]
    }), encoding='utf-8')
    (workspace / 'fileized' / 'json' / 'abc.json').write_text(json.dumps({
        'file_id': 'abc',
        'relative_path': 'sample.dwg',
        'extension': '.dwg',
        'status': 'ok',
        'engine': 'zwcad_saveas_dxf_ezdxf',
        'metadata': {'external_converter_used': True},
        'warnings': [{'type': 'external_converter_used'}],
    }), encoding='utf-8')

    summary = CorpusRunResultSummarizer(workspace).summarize()
    checklist = summary['checklist']
    assert checklist['webhard_sample_run_json_exists'] is True
    assert checklist['quality_audit_md_exists'] is True
    assert checklist['final_report_md_exists'] is True
    assert checklist['staged_dwg_count'] == 1
    assert checklist['dxf_count'] == 1
    assert checklist['dwg_engine_is_zwcad_saveas_dxf_ezdxf'] is True
    assert checklist['external_converter_success_count'] == 1
    assert checklist['external_converter_warning_count'] == 1
    assert checklist['all_pipeline_stages_completed_without_abort'] is True
    assert Path(CorpusRunResultSummarizer(workspace).write_markdown()).exists()


def test_find_files_case_insensitive_deduplicates_suffix_matches(tmp_path: Path):
    root = tmp_path / 'tmp' / 'dxf'
    (root / 'a').mkdir(parents=True)
    dxf = root / 'a' / 'sample.dxf'
    dwg = root / 'a' / 'sample.dwg'
    dxf.write_text('stub', encoding='utf-8')
    dwg.write_text('stub', encoding='utf-8')

    found_dxf = CorpusRunResultSummarizer._find_files_case_insensitive(root, '.dxf')
    found_dwg = CorpusRunResultSummarizer._find_files_case_insensitive(root, '.dwg')

    assert found_dxf == [dxf]
    assert found_dwg == [dwg]


def test_run_result_summarizer_understands_batch_log(tmp_path: Path):
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    (workspace / 'fileized' / 'json').mkdir(parents=True)
    (workspace / 'failures').mkdir()
    (workspace / 'tmp' / 'dxf').mkdir(parents=True)
    (workspace / 'QUALITY_AUDIT.md').write_text('# QA', encoding='utf-8')
    (workspace / 'FINAL_REPORT.md').write_text('# Report', encoding='utf-8')
    (workspace / 'BATCH_RUN.json').write_text(json.dumps({
        'finalize': {
            'validate': {},
            'index': {},
            'learn': {},
            'quality': {},
            'report': {},
        }
    }), encoding='utf-8')

    summary = CorpusRunResultSummarizer(workspace).summarize()
    assert summary['checklist']['batch_run_json_exists'] is True
    assert summary['checklist']['all_pipeline_stages_completed_without_abort'] is True
