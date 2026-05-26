# 164. Agent 2 Candidate Validation Harness

Date: 2026-05-26

## Purpose

This document describes the Agent 2 worker/CLI candidate validation harness.

It is the required bridge between docs-only candidate contracts and the first small registration PR.

## Scope

Added validation file:

```text
tests/test_agent2_candidate_validation_harness.py
```

This harness validates candidates without modifying active registration files.

## What it checks

### Worker candidates

The test imports candidate worker modules and verifies each module exposes `run_worker`.

Candidate worker modules:

```text
src.workers.pdf_raster_worker
src.workers.ocr_text_region_worker
src.workers.ocr_vector_text_match_worker
src.workers.ocr_cad_text_match_worker
src.workers.text_evidence_fusion_worker
src.workers.text_review_queue_worker
src.workers.text_corrections_export_worker
src.workers.text_calibration_report_worker
src.workers.text_weight_suggestions_worker
src.workers.networkx_graph_audit_worker
src.workers.duckdb_export_worker
```

### CLI candidates

The test imports candidate CLI modules but does not modify `src/main.py`.

Candidate CLI modules:

```text
src.app.analysis_shortcut_cli
src.app.cad_platforms_cli
src.app.cross_validate_cli
src.app.fusion_matrix_cli
src.app.layer_analysis_cli
src.app.layer_audit_cli
src.app.open_backends_cli
src.app.shapely_area_match_cli
src.app.shapely_topology_audit_cli
src.app.shapely_topology_cli
src.app.spatial_cli
src.app.spatial_graph_cli
src.app.text_roles_cli
src.app.worker_cli
```

### Temporary manifest only

The harness builds a temporary manifest inside pytest `tmp_path` and runs `WorkerRunner.dry_run` against it.

It does not change:

```text
config/worker_manifest.json
src/main.py
```

## Focused safe worker run checks

The harness runs only safe empty-workspace checks for workers expected to produce warning/unavailable artifacts without external CAD execution:

```text
ocr_text_region
networkx_graph_audit
```

Broader worker execution remains for later per-family PRs.

## Expected validation

```powershell
python -X utf8 -m pytest -q tests/test_agent2_candidate_validation_harness.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
```

## Safety

This harness does not approve actual registration.

Still prohibited:

```text
editing config/worker_manifest.json
editing src/main.py
live CAD execution
ZWCAD COM SendCommand
CHPROP
SAVEAS
DXFOUT
XiCAD alias execution
original DWG mutation
```

## Next step after this harness is merged

Choose exactly one worker family and create a small registration PR.

First recommended worker family:

```text
networkx_graph_audit
```

Reason:

```text
review-only
no CAD mutation
optional dependency degrades to unavailable
single worker module
clear JSON/Markdown outputs
```
