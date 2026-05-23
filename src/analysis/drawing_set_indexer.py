from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import load_fileized_entities, read_json, write_json_and_md


def build_drawing_set_index(workspace: str | Path) -> dict[str, Any]:
    """Build a workspace-level drawing set index.

    This is a practical index for browsing many drawings by file, discipline, sheet type,
    entity counts, layer counts, and available analysis artifacts.
    """
    base = Path(workspace)
    entities = load_fileized_entities(base)
    by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ent in entities:
        by_file[str(ent.get('file_id') or '<NO_FILE>')].append(ent)
    sheet_classifier = read_json(base / 'DRAWING_SHEET_CLASSIFIER.json')
    layer_profile = read_json(base / 'LAYER_PROFILE_SAMPLE.json')
    records = []
    for file_id, rows in sorted(by_file.items(), key=lambda pair: pair[0]):
        layers = sorted({str(r.get('layer') or '<NO_LAYER>') for r in rows})
        type_counts: dict[str, int] = defaultdict(int)
        text_count = 0
        for row in rows:
            et = str(row.get('entity_type') or '')
            type_counts[et] += 1
            if et in {'TEXT', 'MTEXT'}:
                text_count += 1
        records.append({
            'file_id': file_id,
            'relative_path': rows[0].get('relative_path') if rows else '',
            'entity_count': len(rows),
            'layer_count': len(layers),
            'layers_sample': layers[:30],
            'entity_type_counts': dict(sorted(type_counts.items(), key=lambda pair: (-pair[1], pair[0]))[:20]),
            'text_count': text_count,
            'workspace_discipline_guess': (sheet_classifier.get('summary') or {}).get('discipline'),
            'workspace_sheet_type_guess': (sheet_classifier.get('summary') or {}).get('sheet_type'),
        })
    payload = {
        'backend': 'drawing_set_indexer',
        'schema_version': '0.1',
        'summary': {
            'file_count': len(records),
            'entity_count': len(entities),
            'workspace_discipline_guess': (sheet_classifier.get('summary') or {}).get('discipline'),
            'workspace_sheet_type_guess': (sheet_classifier.get('summary') or {}).get('sheet_type'),
            'layer_profile_count': (layer_profile.get('summary') or {}).get('layer_count'),
        },
        'drawings': records,
        'todo': [
            'Promote workspace-level discipline guess to per-file/per-sheet classification.',
            'Add source file path hashes and original format from ingestion stage.',
            'Add page/layout identifiers for multi-sheet PDFs.',
            'Add drawing set grouping by project folder and discipline.',
        ],
        'warnings': ['drawing set classification is currently workspace-level and weak'],
    }
    return write_json_and_md(base, 'DRAWING_SET_INDEX', payload, _markdown(payload))


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    lines = [
        '# Drawing Set Index',
        '',
        f"- File count: `{s.get('file_count')}`",
        f"- Entity count: `{s.get('entity_count')}`",
        f"- Discipline guess: `{s.get('workspace_discipline_guess')}`",
        f"- Sheet type guess: `{s.get('workspace_sheet_type_guess')}`",
        '',
        '| File ID | Entities | Layers | Texts |',
        '|---|---:|---:|---:|',
    ]
    for row in (payload.get('drawings') or [])[:100]:
        lines.append(f"| {row.get('file_id')} | {row.get('entity_count')} | {row.get('layer_count')} | {row.get('text_count')} |")
    lines.append('')
    return '\n'.join(lines)
