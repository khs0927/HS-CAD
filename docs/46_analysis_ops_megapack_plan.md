# 46. Analysis Ops Megapack Plan

This document defines the fourth large-batch analysis branch.

## Goal

Add operational and validation-support modules for large HS-CAD analysis batches.

This PR does not try to finalize drawing semantics. It creates the support layer needed to evaluate, summarize, and operate the growing analysis worker stack.

## Included modules

```text
src/analysis/layer_profile_sampler.py
src/analysis/drawing_sheet_classifier.py
src/analysis/batch_validation_summary_collector.py
src/analysis/quality_dashboard_manifest.py
src/analysis/worker_pipeline_runner.py
src/workers/analysis_ops_megapack_worker.py
```

## New worker

```text
analysis_ops_megapack
```

Command:

```powershell
python -X utf8 -m src.main hscad-worker-run analysis_ops_megapack --workspace outputs\webhard_batch_100
```

## Outputs

```text
LAYER_PROFILE_SAMPLE.json
LAYER_PROFILE_SAMPLE.md
DRAWING_SHEET_CLASSIFIER.json
DRAWING_SHEET_CLASSIFIER.md
BATCH_VALIDATION_SUMMARY.json
BATCH_VALIDATION_SUMMARY.md
VALIDATION_SUMMARY.md
QUALITY_DASHBOARD_MANIFEST.json
QUALITY_DASHBOARD_MANIFEST.md
WORKER_PIPELINE_PLAN.json
WORKER_PIPELINE_PLAN.md
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs/analysis_ops_megapack.jsonl
```

## Included analysis/ops areas

### 1. Layer Profile Sampler

Collects layer statistics without hard-coding company-specific mappings.

Outputs:

```text
layer
entity_count
bbox_count
entity_type_counts
color_counts
linetype_counts
text_samples
weak semantic guess
```

Important rule:

```text
Do not finalize company-specific layer semantics yet.
This is only a sample/statistics artifact.
```

### 2. Drawing Sheet Classifier

Weak workspace-level sheet classifier using:

```text
DRAWING_SHEET_METADATA.json
TITLEBLOCK_KEY_VALUES.json
LAYER_PROFILE_SAMPLE.json
TEXT_ROLE_INFERENCE.json
```

Initial labels:

```text
architectural
structural
electrical
mechanical
fire
civil
unknown
```

Sheet type labels:

```text
plan
section
elevation
detail
schedule
cover
unknown
```

### 3. Batch Validation Summary Collector

Collects expected artifacts and status summaries across the worker stack.

Primary output:

```text
BATCH_VALIDATION_SUMMARY.json
VALIDATION_SUMMARY.md
```

This should be the first artifact checked after every webhard batch run.

### 4. Quality Dashboard Manifest

Creates a manifest for future Streamlit or static HTML dashboards.

Primary output:

```text
QUALITY_DASHBOARD_MANIFEST.json
```

### 5. Worker Pipeline Plan

Creates an ordered analysis pipeline plan.

Current plan:

```text
analysis_core_megapack
analysis_graph_megapack
analysis_advanced_megapack
```

This is currently a plan artifact only. Actual subprocess execution is a future step.

## Validation TODO

Pull branch locally and run:

```powershell
git fetch origin pull/<PR_NUMBER>/head:pr-analysis-ops-megapack
git switch pr-analysis-ops-megapack
git reset --hard FETCH_HEAD

python -m pip install -r requirements.txt
python -m pip install pytest shapely

python -m pytest tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run analysis_core_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_graph_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_advanced_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_ops_megapack --workspace outputs\webhard_batch_100
```

Expected artifacts:

```text
outputs\webhard_batch_100\LAYER_PROFILE_SAMPLE.json
outputs\webhard_batch_100\DRAWING_SHEET_CLASSIFIER.json
outputs\webhard_batch_100\BATCH_VALIDATION_SUMMARY.json
outputs\webhard_batch_100\VALIDATION_SUMMARY.md
outputs\webhard_batch_100\QUALITY_DASHBOARD_MANIFEST.json
outputs\webhard_batch_100\WORKER_PIPELINE_PLAN.json
```

## Batch validation metrics TODO

Collect:

```text
layer_count
sheet_discipline
sheet_type
missing_artifact_count
dashboard_ready_section_count
pipeline_step_count
runtime
warning count
crash count
```

## Safety

No source mutation.

All modules read derived artifacts and write new derived artifacts.

## Next megapack candidates

```text
1. executable worker pipeline runner
2. CI smoke tests for all megapack workers
3. HTML/Streamlit validation dashboard
4. actual STRtree spatial join backend
5. real table cell geometry extraction
6. drawing set indexer by discipline/sheet type
```
