# 45. Analysis Advanced Megapack Plan

This document defines the third large-batch analysis branch.

## Goal

Add advanced analysis modules that begin moving from scaffold-only interpretation toward real geometry reconstruction, spatial candidate pruning, table cell extraction, and titleblock key-value extraction.

Validation is intentionally deferred to webhard batch runs.

## Included modules

```text
src/analysis/real_geometry_polygonizer.py
src/analysis/spatial_index_service.py
src/analysis/table_cell_extractor.py
src/analysis/titleblock_key_value_extractor.py
src/workers/analysis_advanced_megapack_worker.py
```

## New worker

```text
analysis_advanced_megapack
```

Command:

```powershell
python -X utf8 -m src.main hscad-worker-run analysis_advanced_megapack --workspace outputs\webhard_batch_100
```

## Outputs

```text
REAL_GEOMETRY_POLYGONIZER.json
REAL_GEOMETRY_POLYGONIZER.md
SPATIAL_INDEX_SERVICE.json
SPATIAL_INDEX_SERVICE.md
TABLE_CELL_EXTRACTOR.json
TABLE_CELL_EXTRACTOR.md
TITLEBLOCK_KEY_VALUES.json
TITLEBLOCK_KEY_VALUES.md
DRAWING_SHEET_METADATA.json
DRAWING_SHEET_METADATA.md
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs/analysis_advanced_megapack.jsonl
```

## Included analysis areas

### 1. Real Geometry Polygonizer

Optional Shapely backend.

When Shapely is available:

```text
LINE/LWPOLYLINE/POLYLINE-like entities -> LineString approximations
unary_union
polygonize_full
polygons / dangles / cut_edges / invalid_rings
fragment_quality_score
```

When Shapely is unavailable:

```text
status = unavailable
no fatal crash
warning artifact is still generated
```

Current limitations:

```text
uses true vertices only when present in fileized JSON
falls back to bbox diagonal line when vertices are absent
arc/circle segmentation is still TODO
snap tolerance sweep is still TODO
```

### 2. Spatial Index Service

BBox binning service for large drawing candidate pruning.

Outputs:

```text
bins
text_area_candidates
summary.avg_entities_per_bin
summary.text_area_candidate_count
```

Current strategy:

```text
bbox-bearing entities -> grid bins
TEXT_ROLE_INFERENCE + REAL_GEOMETRY_POLYGONIZER/AREA_BOUNDARY_INFERENCE -> text-area candidates
```

Future TODO:

```text
optional Shapely STRtree
per-file/page partitioning
use this index in leader/dimension/table builders
parquet/duckdb persistence for large batches
```

### 3. Table Cell Extractor

Consumes:

```text
TABLE_GRID_DETECTOR.json
fileized/json/*.json
```

Outputs:

```text
TABLE_CELL_EXTRACTOR.json
TABLE_CELL_EXTRACTOR.md
```

Current strategy:

```text
horizontal_count / vertical_count -> estimated rows/cols
cell placeholder generation
table text assignment placeholder
```

Future TODO:

```text
true grid intersection computation
actual cell rectangle extraction
OCR/PDF/CAD text containment
merged cell detection
schedule/titleblock/detail table classification
```

### 4. Titleblock Key-Value Extractor

Consumes:

```text
TITLEBLOCK_CLASSIFIER.json
TEXT_ROLE_INFERENCE.json
```

Outputs:

```text
TITLEBLOCK_KEY_VALUES.json
DRAWING_SHEET_METADATA.json
```

Initial fields:

```text
drawing_title
drawing_number
scale
date
project_name
drawn_by
checked_by
approved_by
```

Current strategy:

```text
pattern-based key detection
inline value extraction after ':' or '：'
normalized_sheet_metadata scaffold
```

Future TODO:

```text
key-value pairing by neighboring table cells
scale/date/drawing number normalization
company/project template calibration
stable downstream DRAWING_SHEET_METADATA schema
```

## Validation TODO

Pull branch locally and run:

```powershell
git fetch origin pull/<PR_NUMBER>/head:pr-analysis-advanced-megapack
git switch pr-analysis-advanced-megapack
git reset --hard FETCH_HEAD

python -m pip install -r requirements.txt
python -m pip install pytest shapely

python -m pytest tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run analysis_core_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_graph_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_advanced_megapack --workspace outputs\webhard_batch_100
```

Expected artifacts:

```text
outputs\webhard_batch_100\REAL_GEOMETRY_POLYGONIZER.json
outputs\webhard_batch_100\SPATIAL_INDEX_SERVICE.json
outputs\webhard_batch_100\TABLE_CELL_EXTRACTOR.json
outputs\webhard_batch_100\TITLEBLOCK_KEY_VALUES.json
outputs\webhard_batch_100\DRAWING_SHEET_METADATA.json
```

## Batch validation metrics TODO

Collect:

```text
polygon_count
dangle_count
cut_edge_count
invalid_ring_count
fragment_quality_score
spatial_bin_count
text_area_candidate_count
table_cell_candidate_count
titleblock_key_value_candidate_count
runtime
warning count
crash count
```

## Safety

No source mutation.

All modules read derived artifacts and write new derived artifacts.

## Next megapack candidates

```text
1. layer_profile_sampler without fixed company mappings
2. drawing_sheet_classifier
3. stable evidence fusion schema for area/text/leader/dimension/table/titleblock
4. quality dashboard artifact generator
5. batch validation summary collector
6. worker pipeline runner for ordered megapack execution
```
