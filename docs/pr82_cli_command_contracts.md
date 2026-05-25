# PR82 CLI Command Contracts

## Introduction

This document outlines the command contracts for the new CLI groups extracted from PR82 (PR #94). Before these command groups can be safely registered in `src/main.py`, they must adhere to the rules established in this contract to ensure the stability of the orchestrator and prevent unauthorized live CAD execution or DWG mutation.

## Target CLI Modules

- `src/app/analysis_shortcut_cli.py`
- `src/app/cad_platforms_cli.py`
- `src/app/cross_validate_cli.py`
- `src/app/fusion_matrix_cli.py`
- `src/app/layer_analysis_cli.py`
- `src/app/layer_audit_cli.py`
- `src/app/open_backends_cli.py`
- `src/app/shapely_area_match_cli.py`
- `src/app/shapely_topology_audit_cli.py`
- `src/app/shapely_topology_cli.py`
- `src/app/spatial_cli.py`
- `src/app/spatial_graph_cli.py`
- `src/app/text_roles_cli.py`
- `src/app/worker_cli.py`

## CLI Command Contract Rules

1. **No Direct CAD Execution**: The CLI commands must not instantiate `ZWCADCOMAdapter`, `AutoCADAdapter`, or invoke `oda_file_converter` for mutation. All extraction must be done via the standardized `WorkerRunner`.
2. **Worker Execution Only**: Instead of running complex logic within the `src/app/*_cli.py` files, commands must delegate tasks to the `WorkerRunner` and specify the exact `worker_name` from `config/worker_manifest.json`.
3. **No Direct Mutation of `main.py`**: Changes to `src/main.py` should only be limited to `import` statements and adding the Typer `app.add_typer` command groups.
4. **Dry-Run by Default**: All destructive commands or those generating massive megapacks must support a `--dry-run` flag to preview the worker pipeline without execution.
5. **Artifact Isolation**: Generated outputs must be routed to `outputs/` or temporary workspaces and never pollute the core repository or source data folders.

## Next Step for Integration

Once this document is reviewed and approved, a separate PR will modify `src/main.py` to import and register these Typer applications. This ensures that any command added to the entrypoint has been fully audited against the Live Runner Policy and the Command Contract.
