# 44. Analysis Graph Megapack Plan

This document defines the second large-batch analysis branch.

## Goal

Add graph/geometry scaffolds for practical CAD drawing interpretation without slowing development through per-file validation gates.

Validation is intentionally deferred to webhard batch runs.

## Included modules

```text
src/analysis/entity_loader.py
src/analysis/geometry_loop_builder.py
src/analysis/leader_graph_builder.py
src/analysis/dimension_graph_builder.py
src/analysis/table_grid_detector.py
src/analysis/titleblock_classifier.py
src/workers/analysis_graph_megapack_worker.py
```

## New worker

```text
analysis_graph_megapack
```

Command:

```powershell
python -X utf8 -m src.main hscad-worker-run analysis_graph_megapack --workspace outputs\webhard_batch_100
```

## Outputs

```text
GEOMETRY_LOOP_BUILDER.json
GEOMETRY_LOOP_BUILDER.md
LEADER_GRAPH.json
LEADER_GRAPH.md
DIMENSION_GRAPH.json
DIMENSION_GRAPH.md
TABLE_GRID_DETECTOR.json
TABLE_GRID_DETECTOR.md
TITLEBLOCK_CLASSIFIER.json
TITLEBLOCK_CLASSIFIER.md
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs/analysis_graph_megapack.jsonl
```

## Included analysis areas

### 1. Shared entity loader

Loads normalized fileized entities from:

```text
fileized/json/*.json
```

Adds common fields:

```text
id
file_id
relative_path
source_json
entity_index
entity_type
```

Utility helpers:

```text
bbox_center
bbox_iou
distance
read_json
write_json_and_md
```

### 2. Geometry loop builder

Initial signals:

```text
closed_polyline
hatch_boundary
line/arc/circle fragment groups
```

Current strategy is scaffold-level grouping by layer and bbox proximity.

TODO:

```text
endpoint graph
snap tolerance sweep
Shapely polygonize_full
arc/circle approximation
invalid ring / dangle / cut edge audit
```

### 3. Leader graph builder

Creates graph nodes:

```text
text
leader_line_candidate
```

Creates edges:

```text
near_leader_candidate
```

TODO:

```text
endpoint-to-text distance
arrowhead block detection
leader polyline path tracing
spatial index for large drawings
fusion with text_role_inference leader_note score
```

### 4. Dimension graph builder

Creates graph nodes:

```text
dimension_entity
dimension_text_candidate
dimension_line_candidate
```

Creates edges:

```text
numeric_text_near_dimension_line_candidate
```

TODO:

```text
extension line detection
arrow/tick detection
dimension chain grouping
numeric text projection to dimension line
unit context inference
```

### 5. Table grid detector

Initial vector line grouping:

```text
horizontal line count
vertical line count
line density by file/layer
near text count
```

TODO:

```text
actual line angle extraction
grid intersection computation
cell rectangle extraction
pdfplumber table/line/rect fusion
OCR table_text fusion
schedule/titleblock/detail table classification
```

### 6. Titleblock classifier

Uses:

```text
TABLE_GRID_DETECTOR candidates
TABLE_REGION_INFERENCE candidates
TEXT_ROLE_INFERENCE title key hits
```

TODO:

```text
sheet boundary detection
lower-right page priors
key-value extraction
drawing title / drawing number / scale / date normalization
company/project template calibration
```

## Validation TODO

Pull branch locally and run:

```powershell
git fetch origin pull/<PR_NUMBER>/head:pr-analysis-graph-megapack
git switch pr-analysis-graph-megapack
git reset --hard FETCH_HEAD

python -m pip install -r requirements.txt
python -m pip install pytest

python -m pytest tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run analysis_graph_megapack --workspace outputs\webhard_batch_100
```

Expected artifacts:

```text
outputs\webhard_batch_100\GEOMETRY_LOOP_BUILDER.json
outputs\webhard_batch_100\LEADER_GRAPH.json
outputs\webhard_batch_100\DIMENSION_GRAPH.json
outputs\webhard_batch_100\TABLE_GRID_DETECTOR.json
outputs\webhard_batch_100\TITLEBLOCK_CLASSIFIER.json
```

## Batch validation metrics TODO

Collect:

```text
geometry closed candidate count
geometry fragment group count
leader graph edge count
dimension graph edge count
table grid candidate count
titleblock candidate count
runtime
warning count
crash count
```

## Safety

No source mutation.

All modules read derived artifacts and write new derived artifacts.

## Next megapack candidates

```text
1. real_geometry_polygonizer using Shapely polygonize_full
2. spatial_index_service with STRtree / bbox bins
3. table_cell_extractor with vector grid intersections
4. titleblock_key_value_extractor
5. drawing_sheet_classifier
6. layer_profile_sampler without fixed company profiles
```
