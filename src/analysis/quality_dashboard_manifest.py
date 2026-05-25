from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.entity_loader import read_json, write_json_and_md

DASHBOARD_SECTIONS = [
    {'id': 'batch_summary', 'title': 'Batch Validation Summary', 'artifact': 'BATCH_VALIDATION_SUMMARY.json'},
    {'id': 'layers', 'title': 'Layer Profile Sample', 'artifact': 'LAYER_PROFILE_SAMPLE.json'},
    {'id': 'sheet', 'title': 'Drawing Sheet Classifier', 'artifact': 'DRAWING_SHEET_CLASSIFIER.json'},
    {'id': 'text_roles', 'title': 'Text Role Inference', 'artifact': 'TEXT_ROLE_INFERENCE.json'},
    {'id': 'geometry', 'title': 'Real Geometry Polygonizer', 'artifact': 'REAL_GEOMETRY_POLYGONIZER.json'},
    {'id': 'spatial', 'title': 'Spatial Index Service', 'artifact': 'SPATIAL_INDEX_SERVICE.json'},
    {'id': 'leader', 'title': 'Leader Graph', 'artifact': 'LEADER_GRAPH.json'},
    {'id': 'dimension', 'title': 'Dimension Graph', 'artifact': 'DIMENSION_GRAPH.json'},
    {'id': 'table', 'title': 'Table Cell Extractor', 'artifact': 'TABLE_CELL_EXTRACTOR.json'},
    {'id': 'titleblock', 'title': 'Titleblock Key Values', 'artifact': 'TITLEBLOCK_KEY_VALUES.json'},
]


def build_quality_dashboard_manifest(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    sections = []
    for section in DASHBOARD_SECTIONS:
        artifact = base / section['artifact']
        payload = read_json(artifact)
        sections.append({
            **section,
            'path': str(artifact),
            'exists': artifact.exists(),
            'summary': payload.get('summary') or {},
            'warning_count': len(payload.get('warnings') or []),
        })
    payload = {
        'backend': 'quality_dashboard_manifest',
        'schema_version': '0.1',
        'summary': {
            'section_count': len(sections),
            'ready_section_count': sum(1 for s in sections if s['exists']),
            'missing_section_count': sum(1 for s in sections if not s['exists']),
        },
        'sections': sections,
        'dashboard_todo': [
            'Build Streamlit or static HTML viewer using this manifest.',
            'Add thumbnail links from pdf_raster/rendered pages.',
            'Add review queue overlays for text/geometry/table/titleblock issues.',
            'Add pass/fail thresholds after validation rules mature.',
        ],
        'warnings': [f"missing dashboard artifact: {s['artifact']}" for s in sections if not s['exists']],
    }
    return write_json_and_md(base, 'QUALITY_DASHBOARD_MANIFEST', payload, _markdown(payload))


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    lines = [
        '# Quality Dashboard Manifest',
        '',
        f"- Sections: `{s.get('section_count')}`",
        f"- Ready: `{s.get('ready_section_count')}`",
        f"- Missing: `{s.get('missing_section_count')}`",
        '',
        '| Section | Artifact | Exists | Warnings |',
        '|---|---|---:|---:|',
    ]
    for row in payload.get('sections') or []:
        lines.append(f"| {row.get('title')} | {row.get('artifact')} | {row.get('exists')} | {row.get('warning_count')} |")
    lines.append('')
    return '\n'.join(lines)
