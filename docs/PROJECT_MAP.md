# Project Map

This project map outlines the structure of the `zwcad-ai-modifier` framework (HS-CAD-clone).

## Directory Structure

- `src/`: Core Python modules for DWG parsing, COM adapter interface, LISP modifiers, and AI integration.
- `scripts/`: Automation and execution scripts for CAD pipelines, scanning, and local verification.
- `tests/`: Unit and integration testing suites utilizing `pytest`.
- `docs/`: Technical manuals, design proposals, architecture manuals, and historical workreports.
- `lisp/`: LISP scripts for direct extraction and block manipulation inside ZWCAD.
- `outputs/`/`output/`: Automated extraction JSON reports, DXF merges, and intermediate output data.
- `config/`: Global workspace and app configurations.
- `data/`: Core static databases and dictionaries.

## Important Entry Points

- Python Entry: `src` modules and CLI commands.
- CAD Adapters: `zwcad_auto_analyze_live_preview.py`, `modify_active_landscape.py`.
- Tests Entry: `tests` directory run via `pytest`.

## Protected Paths

- `prod/`
- `live/`
- `infra/` / `infrastructure/`
- `migrations/` / `database/migrations/`
- `.env*`
