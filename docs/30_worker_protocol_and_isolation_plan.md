# 30. Worker Protocol and Isolation Plan

This document defines PR #7A: HS-CAD Worker Protocol / Isolation Foundation.

## Goal

HS-CAD Core must stay stable and lightweight while heavy open-source backends run as isolated workers.

This is required before adding heavier backends such as:

```text
DuckDB / Polars / PyArrow
NetworkX / rustworkx
OpenCV / PaddleOCR / VLM / Torch
IfcOpenShell
SAM / ColPali / future experimental models
```

## Principles

1. HS-CAD Core owns the artifact contracts.
2. Workers own optional heavy dependencies.
3. Workers must communicate through JSON WorkerInput / WorkerOutput only.
4. Missing or failed workers must not crash the core pipeline.
5. Every WorkerOutput must include provenance.
6. Original DWG/DXF/PDF/image files must not be mutated by workers.
7. License-sensitive or GPU-heavy dependencies must stay outside the default core install.

## Files added in PR #7A

```text
config/worker_manifest.json
src/workers/contracts.py
src/workers/provenance.py
src/workers/registry.py
src/workers/runner.py
src/workers/shapely_topology_worker.py
src/app/worker_cli.py
tests/test_worker_contracts.py
tests/test_worker_runner.py
```

## Worker manifest

The manifest describes workers, requirements, entrypoints, limits, and planned future backends.

Current implemented sample worker:

```text
shapely_topology
```

Planned workers:

```text
networkx_graph_audit
duckdb_export
vision_layout
bim_projection
```

## Commands

List workers:

```powershell
python -X utf8 -m src.main hscad-workers --out-json outputs\WORKERS.json
```

Dry-run a worker command plan:

```powershell
python -X utf8 -m src.main hscad-worker-run shapely_topology --workspace outputs\webhard_batch_100 --dry-run
```

Run the sample Shapely worker:

```powershell
python -X utf8 -m src.main hscad-worker-run shapely_topology --workspace outputs\webhard_batch_100 --snap-tolerance 0.0
```

Expected artifacts:

```text
outputs\webhard_batch_100\SHAPELY_TOPOLOGY.json
outputs\webhard_batch_100\SHAPELY_AREA_MATCHES.json
outputs\webhard_batch_100\SHAPELY_TOPOLOGY_AUDIT.json
```

## WorkerInput

```json
{
  "protocol_version": "1.0",
  "worker_name": "shapely_topology",
  "task": "run",
  "workspace": "outputs/webhard_batch_100",
  "input_artifacts": ["fileized/json", "AREA_ELEMENTS.json"],
  "options": {"snap_tolerance": 0.0},
  "provenance": {}
}
```

## WorkerOutput

```json
{
  "protocol_version": "1.0",
  "worker_name": "shapely_topology",
  "backend": "shapely_topology",
  "status": "ok",
  "artifacts": [
    "SHAPELY_TOPOLOGY.json",
    "SHAPELY_AREA_MATCHES.json",
    "SHAPELY_TOPOLOGY_AUDIT.json"
  ],
  "signals": [],
  "warnings": [],
  "metrics": {},
  "provenance": {}
}
```

## Isolation levels

PR #7A implements the contract and subprocess runner first.

Future isolation levels:

```text
Level 1: current Python subprocess
Level 2: uv run --with requirements
Level 3: project-specific uv virtualenv
Level 4: Docker worker
Level 5: Ray / Dagster / Prefect orchestration wrapper
```

## Validation

Run:

```powershell
python -m pytest tests/test_worker_contracts.py tests/test_worker_runner.py -q
python -X utf8 -m src.main hscad-workers --out-json outputs\WORKERS.json
python -X utf8 -m src.main hscad-worker-run shapely_topology --workspace outputs\webhard_batch_100 --dry-run
python -X utf8 -m src.main hscad-worker-run shapely_topology --workspace outputs\webhard_batch_100 --snap-tolerance 0.0
```

Expected:

```text
outputs\WORKERS.json
outputs\webhard_batch_100\SHAPELY_TOPOLOGY.json
outputs\webhard_batch_100\SHAPELY_AREA_MATCHES.json
outputs\webhard_batch_100\SHAPELY_TOPOLOGY_AUDIT.json
```

## Follow-up PRs

```text
PR #7B: NetworkX Graph Audit worker
PR #8: DuckDB / Parquet analytical export worker
PR #9: PDF / OpenCV raster worker
PR #10: OCR / Layout / VLM worker
PR #13: BIM projection worker
```
