from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


class CorpusQualityAuditor:
    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace)
        self.json_dir = self.workspace / 'fileized' / 'json'

    def audit(self) -> dict[str, Any]:
        records = self._load_records()
        status_counts = Counter(str(record.get('status')) for record in records)
        engine_counts = Counter(str(record.get('engine')) for record in records)
        extension_counts = Counter(str(record.get('extension')) for record in records)
        failure_reasons = Counter()
        warnings_by_type = Counter()
        text_counts_by_file: dict[str, int] = {}
        entity_counts_by_file: dict[str, int] = {}
        low_text_records: list[dict[str, Any]] = []
        unavailable_records: list[dict[str, Any]] = []
        failed_records: list[dict[str, Any]] = []

        for record in records:
            rel = str(record.get('relative_path'))
            text_count = len(record.get('texts') or [])
            entity_count = len(record.get('entities') or [])
            text_counts_by_file[rel] = text_count
            entity_counts_by_file[rel] = entity_count
            if record.get('status') == 'ok' and text_count == 0:
                low_text_records.append({'relative_path': rel, 'engine': record.get('engine'), 'entity_count': entity_count})
            if record.get('status') == 'unavailable':
                unavailable_records.append({'relative_path': rel, 'engine': record.get('engine'), 'warnings': record.get('warnings')})
            if record.get('status') == 'failed':
                failed_records.append({'relative_path': rel, 'engine': record.get('engine'), 'errors': record.get('errors')})
            for item in record.get('errors') or []:
                failure_reasons[str(item.get('type') or item.get('reason') or 'unknown')] += 1
            for item in record.get('warnings') or []:
                warnings_by_type[str(item.get('type') or 'unknown')] += 1

        recommendations = self._recommend(status_counts, engine_counts, low_text_records, failed_records, unavailable_records)
        return {
            'workspace': str(self.workspace),
            'record_count': len(records),
            'status_counts': dict(status_counts),
            'engine_counts': dict(engine_counts),
            'extension_counts': dict(extension_counts),
            'failure_reasons': dict(failure_reasons),
            'warnings_by_type': dict(warnings_by_type),
            'low_text_records': low_text_records[:50],
            'failed_records': failed_records[:50],
            'unavailable_records': unavailable_records[:50],
            'recommendations': recommendations,
        }

    def write_json(self, out: str | Path | None = None) -> str:
        path = Path(out) if out else self.workspace / 'quality_audit.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.audit(), ensure_ascii=False, indent=2), encoding='utf-8')
        return str(path)

    def write_markdown(self, out: str | Path | None = None) -> str:
        audit = self.audit()
        path = Path(out) if out else self.workspace / 'QUALITY_AUDIT.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ['# HS-CAD Corpus Quality Audit', '']
        lines.append(f'- Workspace: `{audit["workspace"]}`')
        lines.append(f'- Records: {audit["record_count"]}')
        lines.append('')
        lines.append('## Status counts')
        for key, value in audit['status_counts'].items():
            lines.append(f'- {key}: {value}')
        lines.append('')
        lines.append('## Engine counts')
        for key, value in audit['engine_counts'].items():
            lines.append(f'- {key}: {value}')
        lines.append('')
        lines.append('## Warnings')
        for key, value in audit['warnings_by_type'].items():
            lines.append(f'- {key}: {value}')
        lines.append('')
        lines.append('## Recommendations')
        for item in audit['recommendations']:
            lines.append(f'- {item}')
        lines.append('')
        if audit['failed_records']:
            lines.append('## Failed samples')
            for item in audit['failed_records'][:20]:
                lines.append(f'- `{item["relative_path"]}` via `{item["engine"]}`')
            lines.append('')
        if audit['unavailable_records']:
            lines.append('## Unavailable samples')
            for item in audit['unavailable_records'][:20]:
                lines.append(f'- `{item["relative_path"]}` via `{item["engine"]}`')
            lines.append('')
        path.write_text('\n'.join(lines), encoding='utf-8')
        return str(path)

    def _load_records(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.json_dir.exists():
            return rows
        for path in sorted(self.json_dir.glob('*.json')):
            try:
                rows.append(json.loads(path.read_text(encoding='utf-8')))
            except Exception as exc:
                rows.append({'status': 'failed', 'engine': 'json_reader', 'relative_path': str(path), 'errors': [{'type': 'json_read_failed', 'reason': str(exc)}]})
        return rows

    @staticmethod
    def _recommend(status_counts: Counter, engine_counts: Counter, low_text_records: list[dict[str, Any]], failed_records: list[dict[str, Any]], unavailable_records: list[dict[str, Any]]) -> list[str]:
        recs: list[str] = []
        if unavailable_records:
            recs.append('Review unavailable engines first. DWG records often require Windows plus ZWCAD COM.')
        if failed_records:
            recs.append('Inspect failures/ and retry only failed files after fixing parser or path issues.')
        if low_text_records:
            recs.append('Files with no extracted text may need OCR, sheet rendering, or CAD-native text extraction improvements.')
        if engine_counts.get('pymupdf', 0) and low_text_records:
            recs.append('For image-only PDFs, add OCR or PDF page raster review in a later stage.')
        if not recs:
            recs.append('No immediate quality blockers found in the sampled corpus.')
        return recs
