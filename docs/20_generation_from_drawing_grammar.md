# Generation From Drawing Grammar

## Purpose
Existing office DWG drawings are not just analysis targets; they become the baseline grammar for all future CAD creation and modification.

## Core Rule
When adding new geometry, first sample the local authoring grammar. Do not decide a new layer; instead, adopt the style used by nearby objects.

## Workflow
1. Identify the target sheet or local region.
2. Locate the nearest `ZIUM_sheet_architect` block if a sheet is involved.
3. Measure the usable drawing area.
4. sample nearby authored geometry (layers, colors, linetypes, lineweights, text heights, dimension styles, leader styles, block effective names).
5. Determine the appropriate entity family.
6. Generate using the sampled layer, color, linetype, lineweight, and text height.
7. Create real `DIMENSION` entities for dimensions.
8. Create real `LEADER`/`QLEADER` entities for callouts.
9. Use block inserts for repeated symbols and title sheets.
10. Place generated geometry within the usable area.
11. Perform a preview **without saving**.
12. Allow an `UNDO BACK` to revert the preview.

## Existing Drawing Edit Policy
- Do not remap layers unless explicitly requested.
- Do not replace the nearby grammar with a new standard.
- Do not explode office blocks.
- Do not bulk‑clear dimension overrides.
- Do not change layout or plot settings automatically.
- Prefer handle‑scoped or region‑scoped edits.

## Standalone Generated Drawing Policy
- Explicit generated layers may be used when the drawing is standalone.
- `QA-REVIEW` layers may be used for review isolation.
- Generated content should still be convertible to office grammar later.

## Sheet Generation
If the user asks to generate a sheet up to the sheet border:
1. Reuse the `ZIUM_sheet_architect` block.
2. Choose an observed insert scale.
3. Place geometry inside the usable area.
4. Use scale‑dependent text and dimension styles.
5. Preserve the title block as a block insert.

## Local Style Sampling
```bash
python tools/sample_style_near_handle.py --handle <HANDLE> --radius 3000 --out-dir outputs/style_sample_current
```
Use the sampled:
- layer
- color
- linetype
- lineweight
- text height
- dimension style
- leader style
- block `EffectiveName`

## ZIUM Sheet Area
```bash
python tools/measure_zium_sheet_usable_area.py --out-dir outputs/zium_sheet_area_current
```
Use the result:
- `usable_area_bbox`
- `title_block_bbox`
- insert scale
- modelspace transformed bounds

## Image‑to‑CAD Application
When converting an image/PDF to CAD:
1. Generate a semantic graph.
2. Convert elements to the office drawing grammar.
3. Apply the sampled layer and entity family.
4. Use `QA-REVIEW` for low‑confidence regions.
5. Insert as a preview block if applying to an existing DWG.
6. Do **not** save automatically.

## Examples
### Example 1
"Add a window near this object."
- Sample surrounding window objects.
- Use the same layer, line style, and block (e.g., `WIN/WINBAR`).
- Generate as a preview.

### Example 2
"Create a section view together with the sheet."
- Insert `ZIUM_sheet_architect`.
- Compute usable area.
- Generate section lines, dimensions, leaders using the sampled styles.
- Place content inside the usable area.

### Example 3
"Overlay an image drawing onto the current drawing."
- Run image‑to‑CAD output.
- Adapt style using the local sample.
- Insert as a preview block.
- Do not save.
