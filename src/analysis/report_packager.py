from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import read_json, write_json_and_md

PACKAGE_PATTERNS = [
    '*.md',
    '*.json',
    '*.html',
    'worker_logs/*.jsonl',
    'worker_pipeline_logs/*.log',
]


def build_report_package_manifest(workspace: str | Path) -> dict[str, Any]:
    """Build a report package manifest.

    This does not create a zip yet. It lists the files that should be included in a shareable
    validation/report bundle.
    """
    base = Path(workspace)
    files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pattern in PACKAGE_PATTERNS:
        for path in sorted(base.glob(pattern)):
            if not path.is_file():
                continue
            rel = str(path.relative_to(base))
            if rel in seen:
                continue
            seen.add(rel)
            files.append({
                'path': rel,
                'size_bytes': path.stat().st_size,
                'category': _category(rel),
            })
    validation = read_json(base / 'VALIDATION_RULE_RESULTS.json')
    payload = {
        'backend': 'report_packager',
        'schema_version': '0.1',
        'summary': {
            'file_count': len(files),
            'total_size_bytes': sum(int(f['size_bytes']) for f in files),
            'validation_status': (validation.get('summary') or {}).get('overall_status'),
        },
        'package_name': f'{base.name}_hscad_validation_report',
        'files': files,
        'zip_todo': {
            'recommended_output': str(base / f'{base.name}_hscad_validation_report.zip'),
            'note': 'Zip creation is intentionally deferred; manifest is safe and reviewable.',
        },
        'todo': [
            'Add actual zip creation with allowlist only.',
            'Add redaction options for private paths and source filenames.',
            'Add package checksum and manifest signing.',
            'Add size limits and optional exclusion of rendered images.',
        ],
        'warnings': ['manifest only; zip file is not created by this scaffold'],
    }
    return write_json_and_md(base, 'REPORT_PACKAGE_MANIFEST', payload, _markdown(payload))


def _category(rel: str) -> str:
    if rel.endswith('.html'):
        return 'dashboard'
    if rel.endswith('.md'):
        return 'markdown_report'
    if rel.endswith('.json'):
        return 'json_artifact'
    if rel.endswith('.jsonl') or rel.endswith('.log'):
        return 'log'
    return 'other'


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    lines = [
        '# Report Package Manifest',
        '',
        f"- Package name: `{payload.get('package_name')}`",
        f"- File count: `{s.get('file_count')}`",
        f"- Total size bytes: `{s.get('total_size_bytes')}`",
        f"- Validation status: `{s.get('validation_status')}`",
        '',
        '| File | Category | Size |',
        '|---|---|---:|',
    ]
    for row in (payload.get('files') or [])[:200]:
        lines.append(f"| {row.get('path')} | {row.get('category')} | {row.get('size_bytes')} |")
    lines.append('')
    return '\n'.join(lines)
