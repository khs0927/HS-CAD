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
