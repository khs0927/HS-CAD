# PR82-S4 NetworkX Graph Audit Extraction Plan

This PR extracts the NetworkX graph audit group from PR82 as an isolated, review-only module.

## Scope

Included:

```text
src/graph/__init__.py
src/graph/networkx_graph_audit.py
src/workers/networkx_graph_audit_worker.py
tests/test_networkx_graph_audit.py
docs/pr82_s4_networkx_graph_audit_plan.md
```

Excluded:

```text
src/main.py
config/worker_manifest.json
outputs/**
artifacts/**/*.zip
live CAD execution
```

## Safety

This module reads `SPATIAL_GRAPH.json`, audits graph consistency, and writes `GRAPH_AUDIT.json` / `GRAPH_AUDIT.md` into the provided workspace.

It does not mutate DWG/DXF files, does not call ZWCAD COM, does not call SendCommand, does not call SaveAs, and does not execute XiCAD aliases.

## Optional dependency behavior

If `networkx` is not installed, the auditor returns `status='unavailable'` instead of failing import-time. This keeps unrelated HS-CAD commands usable in minimal environments.

## Expected validation

```powershell
python -X utf8 -m pytest -q tests/test_networkx_graph_audit.py
python -X utf8 -m compileall -q src/graph src/workers tests
```

## Follow-up

Worker manifest registration should remain a separate candidate-only PR after this module is validated locally.
