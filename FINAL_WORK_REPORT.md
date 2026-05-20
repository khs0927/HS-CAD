# Final Work Report

## Reframed architecture

The framework has been reorganized around validated JSON commands, safety guards, ZWCAD COM fallback, architecture-specific analysis, and XiCAD safe execution.

## Added in this pass

- Architecture audit report module
- Debug bundle collector
- Planned action executor module
- AI planner prompt structure
- Future UI state stubs
- Public release packaging tool
- Integration test skeletons for real ZWCAD
- New validation and packaging tests
- New docs: framework, real validation, AI planner, public release

## Verified

Run:

```powershell
python -m src.main --help
python -m pytest -q
```

## Next priorities

1. Collect real ZWCAD `objects.json` samples.
2. Validate `replace_block` on real DWG copies.
3. Document XiCAD WAL/COL/D1/W1 input flows.
4. Connect PyRx/cad-pyrx after runtime confirmation.
5. Build PySide6 desktop UI.
6. Connect a real LLM provider to the JSON-only planner.

## Added: Architectural Object Semantic Analysis

This iteration added a layer-first semantic classifier for existing drawings. It maps the user-defined ZWCAD layer standard to architectural meanings, then supplements that with geometry/entity heuristics.

New modules:

- `src/semantics/layer_taxonomy.py`
- `src/semantics/object_classifier.py`
- `src/semantics/screen_capture.py`

New CLI commands:

- `layer-taxonomy`
- `classify-objects`
- `capture-screen`

New outputs in `analyze-architecture`:

- `object_semantics.json`
- `semantic_summary.json`
- `object_semantics.xlsx`
- `layer_semantics.xlsx`
- `drawing_semantic_summary.md`

Design rule: semantic classification prioritizes CAD layer/object data. Screenshot capture is available only as a fallback and documentation aid.

## Stabilized After Import

- Re-applied dry-run-first behavior for `run-command`.
- Enforced `--save-as` for mutating `--execute` commands.
- Enforced `--yes` for `delete_layer_objects` execution and protected `0` / `Defpoints` layers in the COM adapter.
- Added fallback built-in Safe Bridge catalog output when XiCAD `Lisp/xiShortkey_origin.key` is absent.
- Made `xicad-safe-plan` accept both positional command paths and `--command`.
- Restored compatibility helpers: `PlannedActionExecutor` and `replace_block_plan`.
- Normalized the layer taxonomy descriptions in code and config so reports use readable layer meanings.
- Verified screen capture is non-fatal and remains a supporting workflow.

Latest non-ZWCAD verification:

```powershell
python -m src.main --help
python -m src.main layer-taxonomy
python -m src.main run-command --dwg "C:/cad/sample.dwg" --command "examples/commands/classify_objects.json" --dry-run
python -m src.main xicad-catalog --xicad-root "../vendor/xicad"
python -m src.main xicad-safe-plan examples/commands/xicad_safe_wall_plan.json
python -m src.main capture-screen --out outputs/test_capture.png
python tools/prepare_public_release.py --help
python -m pytest -q
```

Result: `38 passed, 5 skipped`.
# 2026-05-13 ZWCAD 2025/2026 Compatibility Stabilization

## Completed

- Added `env-check` CLI for ZWCAD 2025/2026 workstation validation.
- Added shared and versioned COM ProgID probing with safe active-instance-first behavior.
- Added 2025/2026 verification tools and safe test plan wrappers.
- Added PowerShell entry scripts for venv setup, environment checks, CLI smoke checks, and safe test plans.
- Expanded semantic classification output with semantic type, structural role, discipline, color standard checks, confidence, warnings, and evidence order.
- Added `examples/sample_objects/layer_semantic_sample.json` for ZWCAD-free semantic testing.
- Added `capture_screen` JSON command support and screen capture metadata output.
- Updated README and compatibility notes for ZWCAD 2025/2026, scan/classify/analyze, screen capture, smoke modify, and public release.

## Verification

- `python -m pytest -q`: passing.
- `python -m src.main env-check --version 2025 --out-dir outputs/zwcad2025_env_check`: generated JSON/Markdown/optional import reports.
- `python -m src.main classify-objects --input-json examples/sample_objects/layer_semantic_sample.json --out outputs/object_semantics.json`: generated semantic JSON from pure sample data.

## Next

1. Run env-check on the target ZWCAD 2025 and 2026 PCs.
2. Capture real `objects.json` from representative DWGs.
3. Review `object_semantics.json` misclassifications and refine the taxonomy.
4. Confirm `MARK` layer dx=0 smoke modify on copied DWGs.
5. Test `replace_text`, `replace_block`, `create_grid`, and XiCAD WAL/COL/D1/W1 on copied DWGs.
