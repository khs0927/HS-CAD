# HS-CAD

HS-CAD is a Windows/ZWCAD automation toolkit for safely reading, auditing, and generating CAD drawings from Python.

The project grew out of real ZWCAD detail-drawing work, so it includes defaults for common drafting expectations:

- Use the user-requested dimension/leader style when one is specified.
- If no style is specified, prefer `복사 ISO-25` when it exists in the DWG.
- If `복사 ISO-25` is not present, fall back to `ISO-25`.
- Create real CAD dimension entities for dimensions, not loose line/text sketches.
- Create real CAD leader entities for callouts, using QLEADER-style ㄴ paths with a horizontal landing next to the text.
- Treat insulation as an area; generate batting geometry on the insulation thickness centerline when thickness-fit matters.
- Avoid guessed `BATTING` linetype scale for generated insulation details.
- Escape non-ASCII text as ZWCAD Unicode codes when COM text insertion would otherwise turn Korean into `??`.

## Install

Run on Windows with ZWCAD installed:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Optional CAD integrations:

```powershell
pip install pyzwcad
pip install cad-pyrx
```

## Core Commands

```powershell
python -m src.main --help
python -m src.main env-check --start-zwcad
python -m src.main scan --dwg "C:/cad/sample.dwg" --out "outputs/objects.json"
python -m src.main list-layers --dwg "C:/cad/sample.dwg"
python -m src.main analyze-architecture --dwg "C:/cad/sample.dwg" --out-dir "outputs/architecture_report"
python -m src.main collect-debug --dwg "C:/cad/sample.dwg" --out-dir "outputs/debug_bundle"
```

## Auto Analysis + Live Preview

For an already-open ZWCAD drawing, HS-CAD can analyze layer aliases and optionally
apply a reversible live preview. Preview mode does not save the DWG.

```powershell
python zwcad_auto_analyze_live_preview.py --out-dir outputs/auto_analysis
python zwcad_auto_analyze_live_preview.py --out-dir outputs/auto_analysis --apply-preview --min-confidence 0.82
python zwcad_auto_analyze_live_preview.py --undo-preview
```

Equivalent module commands:

```powershell
python -m image_to_cad.cli auto-analyze-active --out outputs/auto_analysis
python -m image_to_cad.cli auto-preview-remap --out outputs/auto_analysis --min-confidence 0.82
python -m image_to_cad.cli auto-undo-preview
```

Safety defaults:

- No `Save` or `SaveAs`.
- Creates an `UNDO MARK` before preview changes.
- `UNDO BACK` can restore the preview.
- No purge, delete, explode, or block definition edits.
- Layer `0` is blocked by default; use `--allow-layer-zero` only for high-confidence previews.

## Drawing Grammar Learning

HS-CAD also keeps drawing-grammar notes learned from authored architectural DWGs. These notes are used to make future edits look like they belong in the office drawing, not to rewrite the drawing's layers.

- [Architectural drawing learning baseline](docs/18_architectural_drawing_learning_baseline.md)
- [ZIUM sheet and line grammar](docs/19_zium_sheet_and_line_grammar.md)

Useful active-drawing analysis commands:

```powershell
python tools/fast_scan_active.py --out-dir outputs/active_scan_current
python tools/analyze_active_form_sample.py --out-dir outputs/active_form_analysis_current
```

## Drafting Standards In Code

The drafting defaults live in [drawing_standards.py](src/cad_core/drawing_standards.py).

Important helpers:

- `CADGenerationStandards`: project-wide defaults for annotation style, BATTING, linetype scale, and layers.
- `resolve_annotation_style`: picks the requested style, then `복사 ISO-25`, then `ISO-25`.
- `insulation_batting_pattern_points`: generates a thickness-fit batting pattern on the insulation centerline.
- `qleader_l_route_points`: builds QLEADER-style ㄴ leader routes whose final segment lands horizontally beside the label.
- `measured_dimension_override`: keeps generated dimension text tied to measured geometry.
- `cad_unicode_escape`: writes Korean safely through ZWCAD COM.

The ZWCAD adapter exposes these helpers through:

- `configure_drawing_standards(...)`
- `create_aligned_dimension(...)`
- `create_orthogonal_leader(...)`
- `create_qleader_label(...)`
- `create_insulation_batting_pattern(...)`
- `apply_batting_linetype(...)`
- `auto_correct_scales(...)`

Example:

```python
from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter

adapter = ZWCADCOMAdapter(visible=True)
adapter.connect()
adapter.get_active_document()

adapter.configure_drawing_standards(
    annotation_style=None,      # user did not specify, so use 복사 ISO-25 or ISO-25
    batting_width_mm=100,       # auto-correct BATTING scale for 100T insulation
)

adapter.create_aligned_dimension(
    start=[0, 0, 0],
    end=[1500, 0, 0],
    text_position=[750, 150, 0],
    text_override=None,         # generated dimensions display measured geometry
)

adapter.create_qleader_label(
    target=[1500, 100, 0],
    label_origin=[1800, 300, 0],
    label="브라켓 및 앵커",
)
```

## Safety Rules

- Work on copied DWG files when mutating production drawings.
- Prefer dry-run or scan/report commands before edit commands.
- Use `--save-as` style flows for generated outputs.
- When editing an existing office DWG, prefer the sampled local layer and visual grammar.
- Do not remap existing layers unless explicitly requested.
- Use explicit generated layers only for standalone generated drawings or review-isolation workflows.
- Run tests before publishing changes.

## Tests

```powershell
python -m pytest
```

Integration tests that require a real ZWCAD installation are marked with `integration`.
