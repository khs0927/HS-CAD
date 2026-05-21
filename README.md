# HS-CAD

HS-CAD is a Windows/ZWCAD automation toolkit for safely reading, auditing, and generating CAD drawings from Python.

The project grew out of real ZWCAD detail-drawing work, so it includes defaults for common drafting expectations:

- Use the user-requested dimension/leader style when one is specified.
- If no style is specified, prefer `복사 ISO-25` when it exists in the DWG.
- If `복사 ISO-25` is not present, fall back to `ISO-25`.
- Create real CAD dimension entities for dimensions, not loose line/text sketches.
- Create real CAD leader entities for callouts, using orthogonal ㄱ/ㄴ paths so leaders do not cut through the detail.
- Use the real `BATTING` linetype for insulation instead of manually drawn wave geometry.
- Auto-correct linetype scale before saving generated details.
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

## Drafting Standards In Code

The drafting defaults live in [drawing_standards.py](src/cad_core/drawing_standards.py).

Important helpers:

- `CADGenerationStandards`: project-wide defaults for annotation style, BATTING, linetype scale, and layers.
- `resolve_annotation_style`: picks the requested style, then `복사 ISO-25`, then `ISO-25`.
- `recommend_batting_linetype_scale`: scales BATTING based on insulation width.
- `cad_unicode_escape`: writes Korean safely through ZWCAD COM.

The ZWCAD adapter exposes these helpers through:

- `configure_drawing_standards(...)`
- `create_aligned_dimension(...)`
- `create_orthogonal_leader(...)`
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
    text_override="1,500",
)

adapter.create_orthogonal_leader(
    points=[
        [1500, 100, 0],
        [1800, 100, 0],
        [1800, 300, 0],
    ]
)
```

## Safety Rules

- Work on copied DWG files when mutating production drawings.
- Prefer dry-run or scan/report commands before edit commands.
- Use `--save-as` style flows for generated outputs.
- Keep generated layers explicit so changes can be reviewed and removed cleanly.
- Run tests before publishing changes.

## Tests

```powershell
python -m pytest
```

Integration tests that require a real ZWCAD installation are marked with `integration`.
