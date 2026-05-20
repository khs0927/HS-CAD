# Next Development Plan

1. Capture real `objects.json` outputs from several architectural DWGs.
2. Compare ZWCAD COM object names and properties against the current scanner map.
3. Validate `replace_block`, `delete_layer_objects`, `create_boundary`, `create_grid`, `place_columns`, and `place_beams_2d` on copy drawings.
4. Document XiCAD interactive flows for WAL, COL, D1, W1, PK, STP, ELV and INS.
5. Add fixture-based integration tests using sanitized real scan JSON.
6. Connect a local LLM/GPT planner that only emits validated JSON commands.
7. Add a PySide6 desktop UI for selecting DWG, XiCAD root, command JSON, preview and report output.
