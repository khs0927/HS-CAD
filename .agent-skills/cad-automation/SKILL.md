# CAD Automation Skill

Use this skill for CAD/DWG/ZWCAD/AutoCAD automation.

Project assumptions:
- The user works with CAD drawing analysis and modification.
- Layer semantics may include:
  - COL: structural columns/walls/beams
  - WAL1: lightweight partition
  - WAL2: masonry partition
  - WAL3: partition variant
  - ELE: elevation lines
  - DOOR: doors
  - DOOR_ELE: door elevation
  - WIN: windows
  - WINBAR: window frame/bar
  - WINELE: window elevation
  - STAIR: stairs
  - DIM: dimensions
  - DIMLE: leaders/notes
  - CEN: main column centerlines
  - CEN1: auxiliary centerlines

Rules:
- Never overwrite original DWG files.
- Always create backups before modification.
- Prefer extraction/read-only analysis first.
- Produce JSON reports before write operations.
- Separate parsing, classification, reporting, and modification.
- Use dry-run mode before actual modification.
- Keep ZWCAD COM, PyRx, and LISP adapters modular.
- For ZWCAD 2025/2026, avoid version-specific assumptions unless checked.
- For block/text/layer indexing, preserve coordinates, handles, layer names, colors, object types, and bounding boxes when possible.

Recommended project structure:
src/
  app/
  adapters/
    zwcad_com_adapter.py
    pyrx_adapter.py
    xicad_adapter.py
  ai/
    command_parser.py
    command_validator.py
    safety_guard.py
  integrations/
    xicad_command_catalog.py
    xicad_workflows.py
  modifiers/
    architectural_modifier.py
  reports/
lisp/
  zw_count_blocks.lsp
  zw_extract_texts.lsp
  zw_load_xicad.lsp
tests/
docs/

Verification:
- run unit tests
- run sample extraction
- generate outputs/objects.json
- compare counts before/after
- document limitations
