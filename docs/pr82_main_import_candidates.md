# PR82 Main Import Candidates

Date: 2026-05-25

## Purpose

This document preserves the `src/main.py` CLI import candidates from PR82 without directly modifying `src/main.py`.

Direct modification of `src/main.py` is intentionally blocked until the imported modules are individually validated and the project is in a stable merge window.

## Current main status

Latest checked main SHA:

```text
8be27bec9f79ee80886acb8ab8cb1681de3d74ea
```

Current `main` already contains a large analysis megapack import block and several safety/readiness CLIs. PR82's import list is not safe to blindly overwrite because the two lists have diverged.

## Candidate imports from PR82

The PR82 branch proposed these additional imports beyond the earlier base CLI set:

```python
import src.app.spatial_cli  # noqa: F401,E402
import src.app.text_roles_cli  # noqa: F401,E402
import src.app.open_backends_cli  # noqa: F401,E402
import src.app.spatial_graph_cli  # noqa: F401,E402
import src.app.cad_platforms_cli  # noqa: F401,E402
import src.app.layer_analysis_cli  # noqa: F401,E402
import src.app.layer_audit_cli  # noqa: F401,E402
import src.app.fusion_matrix_cli  # noqa: F401,E402
import src.app.cross_validate_cli  # noqa: F401,E402
import src.app.shapely_topology_cli  # noqa: F401,E402
import src.app.shapely_area_match_cli  # noqa: F401,E402
import src.app.shapely_topology_audit_cli  # noqa: F401,E402
import src.app.worker_cli  # noqa: F401,E402
```

## Review status

Before adding any candidate to `src/main.py`, verify each module exists on latest `main` and imports cleanly:

```powershell
python -X utf8 - <<'PY'
import importlib
modules = [
    'src.app.spatial_cli',
    'src.app.text_roles_cli',
    'src.app.open_backends_cli',
    'src.app.spatial_graph_cli',
    'src.app.cad_platforms_cli',
    'src.app.layer_analysis_cli',
    'src.app.layer_audit_cli',
    'src.app.fusion_matrix_cli',
    'src.app.cross_validate_cli',
    'src.app.shapely_topology_cli',
    'src.app.shapely_area_match_cli',
    'src.app.shapely_topology_audit_cli',
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

Then run:

```powershell
python -X utf8 -m src.main --help
```

## Recommendation

Do not add these imports in the same PR as source extraction.

Create a separate CLI registration PR only after:

1. The target module exists on latest `main`.
2. Import smoke tests pass.
3. `python -X utf8 -m src.main --help` passes.
4. The candidate command names do not collide with existing Typer commands.

## Safety

This candidate document does not approve live CAD execution and does not modify `src/main.py`.
