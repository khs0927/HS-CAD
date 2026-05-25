# 43. Analysis Core Megapack Plan

This document defines the large-batch development branch for practical drawing analysis.

## Why this branch exists

Previous PRs were intentionally small because the project was stabilizing ingestion, workers, OCR evidence, and human review loops.

From this point, small branch/approval cycles become a bottleneck. The goal is now to create a large amount of analysis code quickly and defer validation into explicit TODOs.

## New development rule

```text
Generate more code per branch.
Keep validation as TODO until batch testing is available.
Do not mutate source drawings.
Keep every analysis output as derived artifacts.
```

## Included modules

```text
src/analysis/__init__.py
src/analysis/policy_loader.py
src/analysis/text_role_inference.py
src/analysis/leader_dimension_table_inference.py
src/analysis/area_boundary_inference.py
src/workers/analysis_core_megapack_worker.py
```

## New worker

```text
analysis_core_megapack
```

Command:

```powershell
python -X utf8 -m src.main hscad-worker-run analysis_core_megapack --workspace outputs\webhard_batch_100
```

## Outputs

```text
TEXT_ROLE_INFERENCE.json
TEXT_ROLE_INFERENCE.md
AREA_BOUNDARY_INFERENCE.json
AREA_BOUNDARY_INFERENCE.md
LEADER_NOTE_INFERENCE.json
LEADER_NOTE_INFERENCE.md
DIMENSION_TEXT_INFERENCE.json
DIMENSION_TEXT_INFERENCE.md
TABLE_REGION_INFERENCE.json
TABLE_REGION_INFERENCE.md
TITLEBLOCK_INFERENCE.json
TITLEBLOCK_INFERENCE.md
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs/analysis_core_megapack.jsonl
```

## Included analysis areas

### 1. Policy loader

Loads text fusion policy in this order:

```text
TEXT_FUSION_POLICY.json
TEXT_FUSION_WEIGHT_SUGGESTIONS.json policy_patch
DEFAULT_TEXT_POLICY
```

This closes the loop for future custom policy loading.

### 2. Text role inference

Initial role labels:

```text
room_name
dimension_text
leader_note
table_text
titleblock_text
material_note
drawing_note
sheet_index
unknown
```

This is currently heuristic/scaffold-level.

### 3. Leader note inference

Scaffold only. It links text candidates to nearby LINE/LWPOLYLINE/POLYLINE hints.

TODO: replace nearest-first heuristic with geometry-based endpoint proximity, arrowhead detection, and leader polyline path tracing.

### 4. Dimension text inference

Scaffold only. It collects native DIMENSION entities and numeric-looking text.

TODO: detect dimension lines, extension lines, arrows/ticks, associated numeric text, and unit context.

### 5. Table region inference

Scaffold only. It promotes dense closed regions into table candidates.

TODO: implement actual grid detection using vector lines, pdfplumber lines/rects, raster contours, and OCR layout blocks.

### 6. Titleblock inference

Scaffold only. It promotes table candidates into possible titleblock candidates.

TODO: sheet boundary detection, lower/right page region priors, titleblock key text matching, and project/company template calibration.

### 7. Area boundary inference

Initial candidate signals:

```text
closed_polyline_area
hatch_boundary_area
open_linework_boundary_fragment
```

TODO:

```text
Shapely polygonize_full on LINE/ARC-derived segments
snap tolerance and gap closing report
arc/line/circle mixed loop handling
hatch boundary extraction from ezdxf payload
raster contour cross-check
layer-aware filtering after webhard corpus calibration
```

## Validation TODO

Run after the branch is pulled locally:

```powershell
git fetch origin pull/<PR_NUMBER>/head:pr-analysis-core-megapack
git switch pr-analysis-core-megapack
git reset --hard FETCH_HEAD

python -m pip install -r requirements.txt
python -m pip install pytest

python -m pytest tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run analysis_core_megapack --workspace outputs\webhard_batch_100
```

Expected artifacts:

```text
outputs\webhard_batch_100\TEXT_ROLE_INFERENCE.json
outputs\webhard_batch_100\AREA_BOUNDARY_INFERENCE.json
outputs\webhard_batch_100\LEADER_NOTE_INFERENCE.json
outputs\webhard_batch_100\DIMENSION_TEXT_INFERENCE.json
outputs\webhard_batch_100\TABLE_REGION_INFERENCE.json
outputs\webhard_batch_100\TITLEBLOCK_INFERENCE.json
```

## Webhard batch validation TODO

After local execution, collect:

```text
file count
text role count
area candidate count
leader candidate count
dimension candidate count
table candidate count
titleblock candidate count
worker runtime
crash / warning count
```

## Safety

No source mutation.

All modules read derived artifacts and write new derived artifacts.

## Next megapack candidates

```text
1. geometry_loop_builder: real Shapely polygonize_full + snap tolerance
2. leader_graph_builder: endpoint/arrow/text graph
3. dimension_graph_builder: dimension line + extension line + numeric text graph
4. table_grid_detector: vector/raster hybrid table detection
5. titleblock_classifier: titleblock template and key-value extraction
6. layer_profile_sampler: project/company layer statistics without hard-coded company mapping
```
