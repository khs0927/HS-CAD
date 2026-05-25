# 31. NetworkX Graph Audit Plan

This document defines PR #7B: optional NetworkX Graph Audit Worker.

## Goal

Use NetworkX as an optional backend to audit `SPATIAL_GRAPH.json` and detect structural defects in HS-CAD drawing analysis relationships.

## Why graph audit matters

`SPATIAL_GRAPH.json` connects files, layers, texts, and area candidates. If this graph is structurally weak, later cross-validation, query, reporting, and eventually drawing automation can make incorrect decisions.

Graph audit finds:

```text
unlabeled_area
isolated_text
orphan_layer
file_without_area
disconnected_component
duplicate_label_candidates
layer_semantic_conflict
```

## Files added

```text
src/graph/__init__.py
src/graph/networkx_graph_audit.py
src/workers/networkx_graph_audit_worker.py
tests/test_networkx_graph_audit.py
docs/31_networkx_graph_audit_plan.md
```

## Worker

Worker name:

```text
networkx_graph_audit
```

Manifest status:

```text
implemented
```

Input:

```text
SPATIAL_GRAPH.json
```

Outputs:

```text
GRAPH_AUDIT.json
GRAPH_AUDIT.md
```

## Command

```powershell
python -X utf8 -m src.main hscad-worker-run networkx_graph_audit --workspace outputs\webhard_batch_100
```

The worker run also records:

```text
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs\networkx_graph_audit.jsonl
```

## Graph quality metrics

`GRAPH_AUDIT.json` now includes graph quality metrics usable by confidence scoring.

```text
finding_rate
weighted_issue_score
weighted_finding_rate
graph_penalty
graph_quality_score
severity_counts
finding_type_counts
```

Severity weights:

```text
low    = 0.25
medium = 0.60
high   = 1.00
```

Graph penalty formula:

```text
graph_penalty = min(0.35, weighted_finding_rate * 0.25)
graph_quality_score = 1.0 - graph_penalty
```

`GRAPH_AUDIT.md` reports these metrics for human review.

## Cross-validation integration

`hscad-cross-validate` reads:

```text
GRAPH_AUDIT.json
```

It adds graph relationship signals:

```text
networkx_component_check
orphan_detection
```

These signals prefer `graph_quality_score` when present. If missing, they fallback to:

```text
score = 1.0 - finding_rate
```

## Validation

Run:

```powershell
python -m pytest tests/test_networkx_graph_audit.py tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run networkx_graph_audit --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-cross-validate --workspace outputs\webhard_batch_100
```

Expected files:

```text
outputs\webhard_batch_100\GRAPH_AUDIT.json
outputs\webhard_batch_100\GRAPH_AUDIT.md
outputs\webhard_batch_100\CROSS_VALIDATION.json
outputs\webhard_batch_100\WORKER_RUNS.json
outputs\webhard_batch_100\WORKER_AUDIT.json
outputs\webhard_batch_100\worker_logs\networkx_graph_audit.jsonl
```

## Safety

NetworkX is optional. If unavailable, the worker returns structured `unavailable` and does not mutate drawings or existing graph artifacts.
