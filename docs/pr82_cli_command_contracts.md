# PR82 CLI Command Contracts

Date: 2026-05-26

## Purpose

This document replaces PR #102 with a clean docs-only contract for PR82-derived CLI candidates.

PR #102 is stale because its branch is behind current `main` and includes an `outputs/**` report file. This document keeps only the useful CLI contract content and does not modify `src/main.py`.

## Current baseline

```text
main SHA: 70c8e4df3583fc9fcd8c01937dc7636444eafcf6
```

## Target CLI candidate modules

These candidates came from the PR82 / PR94 extraction flow and must not be registered blindly:

```text
src/app/analysis_shortcut_cli.py
src/app/cad_platforms_cli.py
src/app/cross_validate_cli.py
src/app/fusion_matrix_cli.py
src/app/layer_analysis_cli.py
src/app/layer_audit_cli.py
src/app/open_backends_cli.py
src/app/shapely_area_match_cli.py
src/app/shapely_topology_audit_cli.py
src/app/shapely_topology_cli.py
src/app/spatial_cli.py
src/app/spatial_graph_cli.py
src/app/text_roles_cli.py
src/app/worker_cli.py
```

## Contract rules

### 1. No direct CAD execution

Candidate CLI commands must not:

```text
instantiate ZWCAD COM adapters for mutation
call SendCommand
call CHPROP
call SAVEAS
call DXFOUT
execute XiCAD aliases
mutate original DWG/DXF files
```

### 2. Worker-runner delegation preferred

CLI modules should delegate review/report work to validated workers or analysis modules rather than embedding large logic directly into Typer command handlers.

### 3. Dry-run / review-only by default

Commands that generate reports, command plans, or candidate actions must remain review-only unless a separate safety gate explicitly enables copied-DWG-only execution.

### 4. Artifact isolation

Generated artifacts must go under user-provided workspaces or `outputs/**` and must not be committed.

### 5. Registration must be one family at a time

Do not register all CLI modules in `src/main.py` at once.

Use this order:

```text
1. Confirm candidate module exists on latest main.
2. Run import smoke test.
3. Run command help smoke test.
4. Confirm no command-name collision.
5. Add only one command family to src/main.py.
6. Run full pytest and src.main --help.
7. Merge small PR.
```

## Import smoke test

```powershell
python -X utf8 - <<'PY'
import importlib
modules = [
    'src.app.analysis_shortcut_cli',
    'src.app.cad_platforms_cli',
    'src.app.cross_validate_cli',
    'src.app.fusion_matrix_cli',
    'src.app.layer_analysis_cli',
    'src.app.layer_audit_cli',
    'src.app.open_backends_cli',
    'src.app.shapely_area_match_cli',
    'src.app.shapely_topology_audit_cli',
    'src.app.shapely_topology_cli',
    'src.app.spatial_cli',
    'src.app.spatial_graph_cli',
    'src.app.text_roles_cli',
    'src.app.worker_cli',
]
for module in modules:
    try:
        importlib.import_module(module)
        print('OK', module)
    except Exception as exc:
        print('FAIL', module, type(exc).__name__, exc)
PY
```

## Main help smoke test

After any future registration PR:

```powershell
python -X utf8 -m src.main --help
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
```

## Prohibited in the same PR

A CLI registration PR must not also change:

```text
config/worker_manifest.json
src/adapters/zwcad_com_adapter.py
src/converters/oda_file_converter.py
.github/workflows/*.yml
```

## Decision

This document is a contract only. It does not approve registration and does not modify `src/main.py`.
