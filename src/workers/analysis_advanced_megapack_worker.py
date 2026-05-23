from __future__ import annotations

import sys
from pathlib import Path

from src.analysis.real_geometry_polygonizer import run_real_geometry_polygonizer
from src.analysis.spatial_index_service import build_spatial_index
from src.analysis.table_cell_extractor import extract_table_cells
from src.analysis.titleblock_key_value_extractor import extract_titleblock_key_values
from src.workers.contracts import WorkerInput, WorkerOutput
from src.workers.provenance import build_provenance


WORKER_NAME = 'analysis_advanced_megapack'
BACKEND = 'analysis_advanced_megapack'


def run_worker(worker_input: WorkerInput) -> WorkerOutput:
    workspace = Path(worker_input.workspace)
    provenance = build_provenance(
        workspace=workspace,
        backend=BACKEND,
        algorithm='analysis_advanced_megapack_v0_optional_geometry',
        source_artifacts=worker_input.input_artifacts,
        worker_name=WORKER_NAME,
    )
    artifacts: list[str] = []
    warnings: list[str] = []
    metrics = {}
    try:
        polygonizer = run_real_geometry_polygonizer(workspace)
        spatial_index = build_spatial_index(workspace)
        table_cells = extract_table_cells(workspace)
        title_values = extract_titleblock_key_values(workspace)

        artifacts.extend([
            str(workspace / 'REAL_GEOMETRY_POLYGONIZER.json'),
            str(workspace / 'REAL_GEOMETRY_POLYGONIZER.md'),
            str(workspace / 'SPATIAL_INDEX_SERVICE.json'),
            str(workspace / 'SPATIAL_INDEX_SERVICE.md'),
            str(workspace / 'TABLE_CELL_EXTRACTOR.json'),
            str(workspace / 'TABLE_CELL_EXTRACTOR.md'),
            str(workspace / 'TITLEBLOCK_KEY_VALUES.json'),
            str(workspace / 'TITLEBLOCK_KEY_VALUES.md'),
            str(workspace / 'DRAWING_SHEET_METADATA.json'),
            str(workspace / 'DRAWING_SHEET_METADATA.md'),
        ])
        metrics.update({
            'polygon_count': (polygonizer.get('summary') or {}).get('polygon_count', 0),
            'dangle_count': (polygonizer.get('summary') or {}).get('dangle_count', 0),
            'spatial_bin_count': (spatial_index.get('summary') or {}).get('bin_count', 0),
            'text_area_candidate_count': (spatial_index.get('summary') or {}).get('text_area_candidate_count', 0),
            'table_cell_candidate_count': (table_cells.get('summary') or {}).get('cell_candidate_count', 0),
            'titleblock_key_value_candidate_count': (title_values.get('summary') or {}).get('key_value_candidate_count', 0),
        })
        warnings.extend(polygonizer.get('warnings') or [])
        warnings.extend(spatial_index.get('warnings') or [])
        warnings.extend(table_cells.get('warnings') or [])
        warnings.extend(title_values.get('warnings') or [])
        warnings.append('analysis_advanced_megapack still contains scaffold-level outputs; validation is TODO')
    except Exception as exc:
        return WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message=str(exc), provenance=provenance)

    return WorkerOutput(
        worker_name=WORKER_NAME,
        backend=BACKEND,
        status='warning',
        artifacts=artifacts,
        signals=[
            {
                'id': 'analysis_advanced_megapack',
                'score': 0.55,
                'evidence': ['advanced analysis artifacts generated', 'validation deferred to TODO'],
            }
        ],
        warnings=warnings,
        metrics=metrics,
        provenance=provenance,
    )


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        output = WorkerOutput.error(worker_name=WORKER_NAME, backend=BACKEND, message='missing WorkerInput path argument')
        print(output.to_json())
        return 2
    worker_input = WorkerInput.from_json_file(args[0])
    output = run_worker(worker_input)
    print(output.to_json())
    return 0 if output.status in {'ok', 'warning', 'unavailable'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
