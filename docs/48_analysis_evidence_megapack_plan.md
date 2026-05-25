# 48. Analysis Evidence Megapack Plan

This document defines the sixth large-batch analysis branch.

## Goal

Fuse derived analysis artifacts into an explainable evidence graph, add a validation rule layer, generate a report package manifest, and prepare future CLI shortcuts.

This PR keeps the fast-generation strategy: code first, validation TODO later.

## Included modules

```text
src/analysis/evidence_join_fusion.py
src/analysis/validation_rule_engine.py
src/analysis/report_packager.py
src/analysis/cli_shortcut_plan.py
src/workers/analysis_evidence_megapack_worker.py
```

## New worker

```text
analysis_evidence_megapack
```

Command:

```powershell
python -X utf8 -m src.main hscad-worker-run analysis_evidence_megapack --workspace outputs\webhard_batch_100
```

## Outputs

```text
EVIDENCE_JOIN_FUSION.json
EVIDENCE_JOIN_FUSION.md
VALIDATION_RULE_RESULTS.json
VALIDATION_RULE_RESULTS.md
REPORT_PACKAGE_MANIFEST.json
REPORT_PACKAGE_MANIFEST.md
CLI_SHORTCUT_PLAN.json
CLI_SHORTCUT_PLAN.md
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs/analysis_evidence_megapack.jsonl
```

## Included areas

### 1. Evidence Join Fusion

Reads existing derived artifacts and emits a JSON-first evidence graph.

Input examples:

```text
TEXT_ROLE_INFERENCE.json
REAL_GEOMETRY_POLYGONIZER.json
AREA_BOUNDARY_INFERENCE.json
STRTREE_SPATIAL_JOIN.json
LEADER_GRAPH.json
DIMENSION_GRAPH.json
TITLEBLOCK_KEY_VALUES.json
TABLE_CELL_EXTRACTOR.json
```

Output:

```text
EVIDENCE_JOIN_FUSION.json
```

Graph concepts:

```text
text nodes
area nodes
table nodes
titleblock nodes
TEXT_IN_AREA edges
TEXT_NEAR_LEADER edges
TEXT_NEAR_DIMENSION_LINE edges
TITLEBLOCK_KEY_VALUE edges
```

Future TODO:

```text
Promote graph to DuckDB/Parquet tables.
Add evidence weights and conflict fusion.
Add per-file partitioned evidence graphs.
Feed accepted human corrections back into confidence.
```

### 2. Validation Rule Engine

Checks basic artifact presence and simple warning/metric conditions.

Output:

```text
VALIDATION_RULE_RESULTS.json
```

Current rules include:

```text
required BATCH_VALIDATION_SUMMARY.json
required TEXT_ROLE_INFERENCE.json
required REAL_GEOMETRY_POLYGONIZER.json
required STRTREE_SPATIAL_JOIN.json
required EVIDENCE_JOIN_FUSION.json
evidence graph has nodes
evidence graph has edges
dashboard sections ready
```

Future TODO:

```text
Add configurable validation_rules.json.
Add thresholds based on real webhard baseline.
Add per-discipline rules.
Add CI exit code mapping after rules stabilize.
```

### 3. Report Packager

Builds a manifest of files that should be included in a shareable validation/report bundle.

Output:

```text
REPORT_PACKAGE_MANIFEST.json
```

Current behavior:

```text
manifest only
no zip is created yet
```

Future TODO:

```text
Add actual zip creation with allowlist only.
Add redaction options for private paths and source filenames.
Add package checksum and manifest signing.
Add size limits and optional exclusion of rendered images.
```

### 4. CLI Shortcut Plan

Prepares future shortcut commands:

```text
hscad-analysis-run-all
hscad-analysis-dashboard
hscad-analysis-summary
```

Output:

```text
CLI_SHORTCUT_PLAN.json
```

Current behavior:

```text
plan only
commands are not registered yet
```

## Validation TODO

Pull branch locally and run:

```powershell
git fetch origin pull/<PR_NUMBER>/head:pr-analysis-evidence-megapack
git switch pr-analysis-evidence-megapack
git reset --hard FETCH_HEAD

python -m pip install -r requirements.txt
python -m pip install pytest shapely

python -m pytest tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run analysis_core_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_graph_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_advanced_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_ops_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_automation_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_evidence_megapack --workspace outputs\webhard_batch_100
```

Expected artifacts:

```text
outputs\webhard_batch_100\EVIDENCE_JOIN_FUSION.json
outputs\webhard_batch_100\VALIDATION_RULE_RESULTS.json
outputs\webhard_batch_100\REPORT_PACKAGE_MANIFEST.json
outputs\webhard_batch_100\CLI_SHORTCUT_PLAN.json
```

## Batch validation metrics TODO

Collect:

```text
evidence_node_count
evidence_edge_count
validation_overall_status
validation_error_count
validation_warning_count
report_package_file_count
cli_shortcut_count
runtime
warning count
crash count
```

## Safety

No source mutation.

All modules read derived artifacts and write new derived artifacts.

Report packager currently creates a manifest only. It does not create a zip file.

## Next megapack candidates

```text
1. actual CLI command registrations
2. real report zip packager with redaction options
3. evidence graph DuckDB/Parquet export
4. validation threshold config
5. per-file evidence graph partitioning
6. human review dashboard hooks
```
