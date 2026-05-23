from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import read_json, write_json_and_md


def build_html_validation_dashboard(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    manifest = read_json(base / 'QUALITY_DASHBOARD_MANIFEST.json')
    validation = read_json(base / 'BATCH_VALIDATION_SUMMARY.json')
    html_path = base / 'VALIDATION_DASHBOARD.html'
    sections = manifest.get('sections') or []
    content = _render_html(base, manifest, validation, sections)
    html_path.write_text(content, encoding='utf-8')
    payload = {
        'backend': 'html_validation_dashboard',
        'schema_version': '0.1',
        'summary': {
            'html_path': str(html_path),
            'section_count': len(sections),
            'validation_artifact_count': len(validation.get('artifacts') or []),
        },
        'html_path': str(html_path),
        'warnings': [] if sections else ['QUALITY_DASHBOARD_MANIFEST.json has no sections or is missing'],
        'todo': [
            'Add artifact detail expand/collapse with client-side JavaScript.',
            'Add rendered PDF thumbnails and overlay links.',
            'Add color-coded pass/fail thresholds after validation rules mature.',
            'Add direct links to worker stdout/stderr logs.',
        ],
    }
    return write_json_and_md(base, 'HTML_VALIDATION_DASHBOARD', payload, _markdown(payload))


def _render_html(base: Path, manifest: dict[str, Any], validation: dict[str, Any], sections: list[dict[str, Any]]) -> str:
    val_summary = validation.get('summary') or {}
    cards = []
    for section in sections:
        title = html.escape(str(section.get('title') or section.get('id')))
        artifact = html.escape(str(section.get('artifact') or ''))
        exists = bool(section.get('exists'))
        warning_count = int(section.get('warning_count') or 0)
        summary = html.escape(str(section.get('summary') or {}))
        status_class = 'ok' if exists and warning_count == 0 else ('warn' if exists else 'missing')
        cards.append(f'''
        <section class="card {status_class}">
          <h2>{title}</h2>
          <p><strong>Artifact:</strong> {artifact}</p>
          <p><strong>Exists:</strong> {exists}</p>
          <p><strong>Warnings:</strong> {warning_count}</p>
          <pre>{summary}</pre>
        </section>
        ''')
    return f'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <title>HS-CAD Validation Dashboard</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; background: #f7f7f7; color: #222; }}
    header {{ background: white; border-radius: 14px; padding: 20px; box-shadow: 0 2px 12px rgba(0,0,0,.06); margin-bottom: 18px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
    .card {{ background: white; border-radius: 14px; padding: 16px; box-shadow: 0 2px 12px rgba(0,0,0,.06); border-left: 6px solid #aaa; }}
    .ok {{ border-left-color: #2e7d32; }}
    .warn {{ border-left-color: #f9a825; }}
    .missing {{ border-left-color: #c62828; }}
    pre {{ white-space: pre-wrap; font-size: 12px; background: #f1f1f1; padding: 10px; border-radius: 8px; }}
  </style>
</head>
<body>
  <header>
    <h1>HS-CAD Validation Dashboard</h1>
    <p><strong>Workspace:</strong> {html.escape(str(base))}</p>
    <p><strong>Expected artifacts:</strong> {html.escape(str(val_summary.get('expected_artifact_count')))}</p>
    <p><strong>Existing artifacts:</strong> {html.escape(str(val_summary.get('existing_artifact_count')))}</p>
    <p><strong>Missing artifacts:</strong> {html.escape(str(val_summary.get('missing_artifact_count')))}</p>
  </header>
  <main class="grid">
    {''.join(cards)}
  </main>
</body>
</html>'''


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    return '\n'.join([
        '# HTML Validation Dashboard',
        '',
        f"- HTML path: `{s.get('html_path')}`",
        f"- Section count: `{s.get('section_count')}`",
        f"- Validation artifact count: `{s.get('validation_artifact_count')}`",
        '',
    ])
