# 47. Analysis Automation Megapack Plan

This document defines the fifth large-batch analysis branch.

## Goal

Add automation, dashboard, drawing-set indexing, and optional STRtree spatial join scaffolds on top of the analysis ops stack.

This PR keeps the fast-generation strategy: code first, validation TODO later.

## Included modules

```text
src/analysis/executable_worker_pipeline_runner.py
src/analysis/html_validation_dashboard.py
src/analysis/drawing_set_indexer.py
src/analysis/strtree_spatial_join_backend.py
src/workers/analysis_automation_megapack_worker.py
```

## New worker

```text
analysis_automation_megapack
```

Command:

```powershell
python -X utf8 -m src.main hscad-worker-run analysis_automation_megapack --workspace outputs\webhard_batch_100
```

Default behavior:

```text
pipeline execution is dry-run by default
```

## Outputs

```text
EXECUTABLE_WORKER_PIPELINE_RUN.json
EXECUTABLE_WORKER_PIPELINE_RUN.md
STRTREE_SPATIAL_JOIN.json
STRTREE_SPATIAL_JOIN.md
DRAWING_SET_INDEX.json
DRAWING_SET_INDEX.md
HTML_VALIDATION_DASHBOARD.json
HTML_VALIDATION_DASHBOARD.md
VALIDATION_DASHBOARD.html
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs/analysis_automation_megapack.jsonl
```

## Included areas

### 1. Executable Worker Pipeline Runner

Reads:

```text
WORKER_PIPELINE_PLAN.json
```

Writes:

```text
EXECUTABLE_WORKER_PIPELINE_RUN.json
EXECUTABLE_WORKER_PIPELINE_RUN.md
worker_pipeline_logs/*.stdout.log
worker_pipeline_logs/*.stderr.log
```

Safety:

```text
dry_run=true by default
```

Future TODO:

```text
non-shell argv mode
resume-from-step
retry support
artifact diff after each worker step
CI-friendly status mode
```

### 2. HTML Validation Dashboard

Reads:

```text
QUALITY_DASHBOARD_MANIFEST.json
BATCH_VALIDATION_SUMMARY.json
```

Writes:

```text
VALIDATION_DASHBOARD.html
HTML_VALIDATION_DASHBOARD.json
HTML_VALIDATION_DASHBOARD.md
```

Future TODO:

```text
artifact detail expand/collapse
rendered PDF thumbnail links
overlay links
color-coded pass/fail thresholds
worker stdout/stderr links
```

### 3. Drawing Set Indexer

Reads:

```text
fileized/json/*.json
DRAWING_SHEET_CLASSIFIER.json
LAYER_PROFILE_SAMPLE.json
```

Writes:

```text
DRAWING_SET_INDEX.json
DRAWING_SET_INDEX.md
```

Initial per-file fields:

```text
file_id
relative_path
entity_count
layer_count
layers_sample
entity_type_counts
text_count
workspace_discipline_guess
workspace_sheet_type_guess
```

Future TODO:

```text
per-file/per-sheet classification
source file path hashes
multi-sheet PDF page identifiers
project folder grouping
```

### 4. STRtree Spatial Join Backend

Optional Shapely backend.

Reads:

```text
REAL_GEOMETRY_POLYGONIZER.json
AREA_BOUNDARY_INFERENCE.json
TEXT_ROLE_INFERENCE.json
fileized/json/*.json fallback
```

Writes:

```text
STRTREE_SPATIAL_JOIN.json
STRTREE_SPATIAL_JOIN.md
```

Current strategy:

```text
area bbox -> Shapely box
text bbox center -> Shapely Point
STRtree query
text_center_in_area_bbox joins
```

If Shapely is unavailable:

```text
status = unavailable
no fatal crash
warning artifact is generated
```

Future TODO:

```text
true polygon geometry instead of bbox geometry
per-file/page partitioning
compare against SPATIAL_INDEX_SERVICE bbox-bin candidates
feed joins back into text/area confidence fusion
```

## Validation TODO

Pull branch locally and run:

```powershell
git fetch origin pull/<PR_NUMBER>/head:pr-analysis-automation-megapack
git switch pr-analysis-automation-megapack
git reset --hard FETCH_HEAD

python -m pip install -r requirements.txt
python -m pip install pytest shapely

python -m pytest tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run analysis_core_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_graph_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_advanced_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_ops_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_automation_megapack --workspace outputs\webhard_batch_100
```

Expected artifacts:

```text
outputs\webhard_batch_100\EXECUTABLE_WORKER_PIPELINE_RUN.json
outputs\webhard_batch_100\STRTREE_SPATIAL_JOIN.json
outputs\webhard_batch_100\DRAWING_SET_INDEX.json
outputs\webhard_batch_100\HTML_VALIDATION_DASHBOARD.json
outputs\webhard_batch_100\VALIDATION_DASHBOARD.html
```

## Batch validation metrics TODO

Collect:

```text
pipeline_error_count
pipeline_dry_run_count
strtree_join_count
drawing_set_file_count
dashboard_section_count
runtime
warning count
crash count
```

## Safety

No source mutation.

All modules read derived artifacts and write new derived artifacts.

Pipeline execution defaults to dry-run.

## Next megapack candidates

```text
1. real pipeline CLI with safe argv execution
2. static dashboard asset bundling
3. evidence fusion for text-area joins
4. per-file sheet classifier
5. validation rule threshold config
6. report packager for sharing results
```
