from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.entity_loader import bbox_center, load_fileized_entities, read_json, write_json_and_md

TEXT_TYPES = {'TEXT', 'MTEXT'}
LINE_TYPES = {'LINE', 'LWPOLYLINE', 'POLYLINE'}


def extract_table_cells(workspace: str | Path) -> dict[str, Any]:
    """Extract table cell candidates from table grid detector output.

    This scaffold creates table-level cell placeholders and attaches nearby text samples.
    A future implementation should compute true grid intersections and cell rectangles.
    """
    base = Path(workspace)
    grid_payload = read_json(base / 'TABLE_GRID_DETECTOR.json')
    entities = load_fileized_entities(base)
    texts = [e for e in entities if e.get('entity_type') in TEXT_TYPES]
    cells: list[dict[str, Any]] = []
    table_texts: list[dict[str, Any]] = []
    for table_idx, cand in enumerate(grid_payload.get('candidates') or []):
        table_id = str(cand.get('grid_id') or f'table:{table_idx}')
        h = int(cand.get('horizontal_count') or 0)
        v = int(cand.get('vertical_count') or 0)
        estimated_rows = max(0, h - 1)
        estimated_cols = max(0, v - 1)
        cell_count = min(estimated_rows * estimated_cols, 500)
        for i in range(cell_count):
            cell_id = f'{table_id}:cell:{i}'
            cells.append({
                'cell_id': cell_id,
                'table_id': table_id,
                'row_index': i // max(estimated_cols, 1),
                'col_index': i % max(estimated_cols, 1),
                'bbox': None,
                'confidence': 0.20,
                'reason': 'estimated_from_line_counts_scaffold',
            })
        for text in texts[:200]:
            table_texts.append({
                'table_id': table_id,
                'text_id': text.get('id'),
                'text': text.get('text') or text.get('value') or text.get('content'),
                'bbox': text.get('bbox'),
                'confidence': 0.15,
                'reason': 'table_text_assignment_pending_geometry',
            })
    payload = {
        'backend': 'table_cell_extractor',
        'schema_version': '0.1',
        'summary': {
            'table_candidate_count': len(grid_payload.get('candidates') or []),
            'cell_candidate_count': len(cells),
            'table_text_candidate_count': len(table_texts),
        },
        'cells': cells,
        'table_texts': table_texts[:5000],
        'todo': [
            'Compute true horizontal/vertical line intersections.',
            'Build actual cell rectangles from adjacent grid lines.',
            'Assign text to cell by bbox containment and OCR/PDF coordinate contract.',
            'Detect merged cells and header/body regions.',
            'Classify schedule/table/titleblock/detail-note grids.',
        ],
        'warnings': ['scaffold only; cell bboxes are not computed yet'],
    }
    return write_json_and_md(base, 'TABLE_CELL_EXTRACTOR', payload, _markdown(payload))


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get('summary') or {}
    return '\n'.join([
        '# Table Cell Extractor',
        '',
        f"- Table candidates: `{s.get('table_candidate_count')}`",
        f"- Cell candidates: `{s.get('cell_candidate_count')}`",
        f"- Table text candidates: `{s.get('table_text_candidate_count')}`",
        '',
    ])
