# 165. NetworkX Graph Audit Worker Registration

Date: 2026-06-30

## Purpose

This PR is the first small worker-registration hardening step after the Agent 2 candidate validation harness.

The worker was already present in `config/worker_manifest.json` as a simple `path` entry. This update expands only the `networkx_graph_audit` entry with review-only safety metadata.

## Scope

Changed files:

```text
config/worker_manifest.json
tests/test_networkx_graph_audit_manifest_registration.py
docs/165_networkx_graph_audit_worker_registration.md
```

## Safety

The registered worker is review-only.

It does not:

```text
run CAD
call SendCommand
call SaveAs
call DXFOUT
execute XiCAD aliases
mutate original DWG/DXF files
```

## Optional dependency

`networkx` is optional. The worker module must remain import-safe even if `networkx` is not installed. Actual graph audit execution should return unavailable or a safe warning if the optional dependency is missing.

## Validation

```powershell
python -X utf8 -m pytest -q tests/test_networkx_graph_audit_manifest_registration.py
python -X utf8 -m pytest -q tests/test_agent2_candidate_validation_harness.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m src.main --help
```

## Next worker family

Do not register another worker in this same PR. After merge and local validation, choose the next worker family in a separate PR.
