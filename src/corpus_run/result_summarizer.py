from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


class CorpusRunResultSummarizer:
    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace)

    def summarize(self) -> dict[str, Any]:
        fileized_dir = self.workspace / 'fileized' / 'json'
        failures_dir = self.workspace / 'failures'
        tmp_dxf_dir = self.workspace / 'tmp' / 'dxf'
        webhard_log = self.workspace / 'webhard_sample_run.json'
        quality_md = self.workspace / 'QUALITY_AUDIT.md'
        final_report = self.workspace / 'FINAL_REPORT.md'

        fileized_records = self._read_json_files(fileized_dir)
        failure_records = self._read_json_files(failures_dir)
        dwg_records = [r for r in fileized_records if str(r.get('extension', '')).lower() == '.dwg']
        failure_error_types = Counter(self._error_type(r) for r in failure_records)
        failure_engines = Counter(str(r.get('engine') or 'unknown') for r in failure_records)
        engines = Counter(str(r.get('engine') or 'unknown') for r in fileized_records)
        status_counts = Counter(str(r.get('status') or 'unknown') for r in fileized_records)

        staged_dwgs = sorted(tmp_dxf_dir.rglob('*.dwg')) if tmp_dxf_dir.exists() else []
        dxf_files = sorted(tmp_dxf_dir.rglob('*.dxf')) + sorted(tmp_dxf_dir.rglob('*.DXF')) if tmp_dxf_dir.exists() else []

        checklist = {
            'webhard_sample_run_json_exists': webhard_log.exists(),
            'quality_audit_md_exists': quality_md.exists(),
            'final_report_md_exists': final_report.exists(),
            'staged_dwg_count': len(staged_dwgs),
            'dxf_count': len(dxf_files),
            'dwg_engine_is_zwcad_saveas_dxf_ezdxf': all(r.get('engine') == 'zwcad_saveas_dxf_ezdxf' for r in dwg_records) if dwg_records else None,
            'external_converter_success_count': sum(1 for r in dwg_records if (r.get('metadata') or {}).get('external_converter_used') is True),
            'external_converter_warning_count': self._warning_count(dwg_records, 'external_converter_used'),
            'zwcad_fallback_attempted_when_oda_unavailable_or_failed': self._fallback_observed(dwg_records, failure_records),
            'failure_error_types': dict(failure_error_types),
            'all_pipeline_stages_completed_without_abort': self._all_stages_completed(webhard_log),
        }

        return {
            'workspace': str(self.workspace),
            'exists': self.workspace.exists(),
            'checklist': checklist,
            'counts': {
                'fileized_json_count': len(fileized_records),
                'failure_json_count': len(failure_records),
                'staged_dwg_count': len(staged_dwgs),
                'dxf_count': len(dxf_files),
                'status_counts': dict(status_counts),
                'engine_counts': dict(engines),
                'failure_error_types': dict(failure_error_types),
                'failure_engines': dict(failure_engines),
            },
            'failure_samples': [self._failure_sample(r) for r in failure_records[:20]],
            'dxf_samples': [str(p) for p in dxf_files[:20]],
            'staged_dwg_samples': [str(p) for p in staged_dwgs[:20]],
            'files': {
                'webhard_sample_run_json': str(webhard_log),
                'quality_audit_md': str(quality_md),
                'final_report_md': str(final_report),
                'fileized_dir': str(fileized_dir),
                'failures_dir': str(failures_dir),
                'tmp_dxf_dir': str(tmp_dxf_dir),
            },
        }

    def write_json(self, out: str | Path | None = None) -> str:
        target = Path(out) if out else self.workspace / 'RUN_SUMMARY.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.summarize(), ensure_ascii=False, indent=2), encoding='utf-8')
        return str(target)

    def write_markdown(self, out: str | Path | None = None) -> str:
        target = Path(out) if out else self.workspace / 'RUN_SUMMARY.md'
        target.parent.mkdir(parents=True, exist_ok=True)
        summary = self.summarize()
        checklist = summary['checklist']
        counts = summary['counts']
        lines = [
            '# HS-CAD Corpus Run Summary',
            '',
            f'- Workspace: `{summary["workspace"]}`',
            f'- Workspace exists: {summary["exists"]}',
            '',
            '## Checklist',
            f'1. `webhard_sample_run.json`: {self._yes(checklist["webhard_sample_run_json_exists"])}',
            f'2. `QUALITY_AUDIT.md`: {self._yes(checklist["quality_audit_md_exists"])}',
            f'3. `FINAL_REPORT.md`: {self._yes(checklist["final_report_md_exists"])}',
            f'4. Staged DWG count under `tmp/dxf`: {checklist["staged_dwg_count"]}',
            f'5. DXF count under `tmp/dxf`: {checklist["dxf_count"]}',
            f'6. DWG record engine is `zwcad_saveas_dxf_ezdxf`: {self._yes(checklist["dwg_engine_is_zwcad_saveas_dxf_ezdxf"])}',
            f'7. `external_converter_used: true` DWG success count: {checklist["external_converter_success_count"]}',
            f'8. `external_converter_used` warning count: {checklist["external_converter_warning_count"]}',
            f'9. ZWCAD fallback observed after ODA unavailable/failure: {self._yes(checklist["zwcad_fallback_attempted_when_oda_unavailable_or_failed"])}',
            f'10. Failure error types: `{json.dumps(checklist["failure_error_types"], ensure_ascii=False)}`',
            f'11. Pipeline completed without abort: {self._yes(checklist["all_pipeline_stages_completed_without_abort"])}',
            '',
            '## Counts',
        ]
        for key, value in counts.items():
            lines.append(f'- {key}: `{json.dumps(value, ensure_ascii=False)}`')
        if summary['failure_samples']:
            lines += ['', '## Failure samples']
            for item in summary['failure_samples']:
                lines.append(f'- `{item["relative_path"]}` | `{item["engine"]}` | `{item["error_type"]}` | {item["reason"][:240]}')
        if summary['dxf_samples']:
            lines += ['', '## DXF samples'] + [f'- `{item}`' for item in summary['dxf_samples']]
        if summary['staged_dwg_samples']:
            lines += ['', '## Staged DWG samples'] + [f'- `{item}`' for item in summary['staged_dwg_samples']]
        target.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        return str(target)

    @staticmethod
    def _read_json_files(directory: Path) -> list[dict[str, Any]]:
        if not directory.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(directory.glob('*.json')):
            try:
                rows.append(json.loads(path.read_text(encoding='utf-8')))
            except Exception as exc:
                rows.append({'relative_path': str(path), 'status': 'failed', 'engine': 'json_reader', 'errors': [{'type': 'json_read_failed', 'reason': str(exc)}]})
        return rows

    @staticmethod
    def _error_type(record: dict[str, Any]) -> str:
        errors = record.get('errors') or []
        if errors and isinstance(errors, list):
            first = errors[0] or {}
            return str(first.get('type') or first.get('error_type') or 'unknown')
        return str(record.get('error_type') or 'unknown')

    @staticmethod
    def _warning_count(records: list[dict[str, Any]], warning_type: str) -> int:
        count = 0
        for record in records:
            for warning in record.get('warnings') or []:
                if warning.get('type') == warning_type:
                    count += 1
        return count

    def _fallback_observed(self, fileized_records: list[dict[str, Any]], failure_records: list[dict[str, Any]]) -> bool:
        if any((r.get('metadata') or {}).get('command_fallback_used') for r in fileized_records):
            return True
        return any('sendcommand' in json.dumps(r, ensure_ascii=False).lower() for r in failure_records)

    @staticmethod
    def _all_stages_completed(webhard_log: Path) -> bool:
        if not webhard_log.exists():
            return False
        try:
            payload = json.loads(webhard_log.read_text(encoding='utf-8'))
        except Exception:
            return False
        stages = payload.get('stages') or []
        names = [item.get('stage') for item in stages if item.get('status') == 'ok']
        required = ['prepare', 'fileize', 'validate', 'index', 'learn', 'quality', 'report']
        return all(name in names for name in required)

    @staticmethod
    def _failure_sample(record: dict[str, Any]) -> dict[str, str]:
        errors = record.get('errors') or []
        first = errors[0] if errors else {}
        return {
            'relative_path': str(record.get('relative_path') or record.get('source_path') or ''),
            'engine': str(record.get('engine') or ''),
            'error_type': str(first.get('type') or record.get('error_type') or 'unknown'),
            'reason': str(first.get('reason') or record.get('reason') or ''),
        }

    @staticmethod
    def _yes(value: Any) -> str:
        if value is True:
            return '✅ yes'
        if value is False:
            return '❌ no'
        return '— not applicable'
