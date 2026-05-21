# Architectural Drawing Learning Baseline

This document records the drawing grammar that HS-CAD should learn from authored architectural DWGs. It is not a report about one specific project file. The purpose is to make future edits easier by understanding how the office drawings are normally composed.

## Core Interpretation

Existing architectural drawings are treated as authored references. Their geometry, symbols, dimensions, text, sheets, and graphic conventions are examples of how future generated or modified drawings should behave.

The goal is not to normalize every drawing into a new standard. The goal is to preserve the existing drawing language and edit within it.

## What To Learn From Existing Drawings

When scanning a DWG, extract these patterns:

- Sheet/title-block block names, insertion scale, rotation, and row/column placement.
- Drawing area inside the sheet.
- Typical entity mix: line, polyline, arc, circle, hatch, text, dimension, leader, insert.
- Color, linetype, lineweight, and ByLayer/ByBlock usage.
- Text style and text height families by sheet scale.
- Dimension styles, scale factors, and whether overrides are present.
- Leader style and route shape.
- Repeated block symbols and office title/sheet blocks.
- Hatch, insulation, centerline, hidden line, fixture, opening, wall, grid, and detail-line expression.

Layer names may be recorded as context, but they are not the primary target of this learning pass.

## What Not To Do By Default

- Do not remap layers just because an alias can be recognized.
- Do not delete, purge, explode, or flatten existing content.
- Do not bulk-clear dimension overrides without understanding drawing intent.
- Do not replace office sheet blocks with newly drawn rectangles.
- Do not introduce a new line grammar when nearby authored geometry already gives one.

## Future Editing Flow

For any future drawing modification:

1. Identify the active sheet or local drawing region.
2. Find nearby authored geometry that plays the same role as the requested new geometry.
3. Sample its color, linetype, lineweight, entity type, text height, dimension style, and block usage.
4. Generate or modify geometry using that local grammar.
5. Keep layers unchanged unless the user explicitly asks for layer work.
6. Prefer handle-scoped or region-scoped changes over broad drawing-wide edits.
7. Save to a copy first unless the user explicitly asks to change the active DWG.

## Sheet Creation Rule

When the user asks for a drawing "with the sheet/title border" (`도곽까지 같이 생성`):

1. Reuse the office sheet block if it exists in the drawing.
2. For ZIUM office drawings, prefer `ZIUM_sheet_architect`.
3. Insert the sheet block at an existing observed scale or a user-specified scale.
4. Place generated drawing content inside the sheet's usable drawing area.
5. Match the text, dimension, leader, and line expression to the sheet scale.

## Dimension And Annotation Rule

- New dimensions should be real dimension entities.
- Dimension values should normally come from measured geometry.
- Existing dimension overrides are treated as authored intent until proven otherwise.
- New leaders should be real CAD leader entities.
- Where the office drawing uses QLEADER-style bent leaders, generated leaders should follow that shape.
- Text height should be inferred from the sheet scale or nearby equivalent annotation.

## Line Expression Rule

Line expression is learned from the drawing's authored graphics:

- Use ByLayer/ByBlock when the surrounding drawing does.
- Reuse nearby linetype families for hidden, center, dashed, and construction lines.
- Reuse nearby color and lineweight conventions.
- Prefer the same entity family used nearby: line, polyline, arc, circle, hatch, or block insert.

## Analysis Tools

Use these tools to gather learning data from the active drawing:

```powershell
python tools/fast_scan_active.py --out-dir outputs/active_scan_current
python tools/analyze_active_form_sample.py --out-dir outputs/active_form_analysis_current
python tools/analyze_active_drawing_visuals.py --out-dir outputs/active_visual_current
```

The outputs are evidence for future behavior, not automatic instructions to rewrite the drawing.
