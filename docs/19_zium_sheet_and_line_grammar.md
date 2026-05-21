# ZIUM Sheet And Line Grammar

This document records recurring sheet and line-expression grammar observed in ZIUM office architectural drawings. It is learning material for future generation and modification, not a one-off judgment about a single DWG.

## Scope

The analysis focuses on sheet form, entity types, line expression, annotation style, and drawing placement. It intentionally does not propose layer remapping. Existing layers remain as authored unless a later user request explicitly targets them.

Example evidence captured during analysis:

- Example DWG: `서대신동 상가주택0702.dwg`
- Example ModelSpace object count: 103,027
- Analysis output: `outputs/active_form_analysis_current/sample_form_analysis.json`
- Repro command: `python tools/analyze_active_form_sample.py --out-dir outputs/active_form_analysis_current`

## Sheet Form

The office title sheet is not drawn ad hoc. It is inserted as a block:

- Block name: `ZIUM_sheet_architect`
- Insert layer observed: `A-FORM`
- Count in the analyzed example: 61
- Rotation: `0.0` for sampled inserts

Observed title block insertion scales:

| X/Y scale | Count | Interpretation |
|---:|---:|---|
| `0.504032` | 31 | dominant observed sheet scale |
| `0.5` | 10 | half-scale sheet family |
| `0.75` | 8 | larger sheet/detail family |
| `0.604839` | 6 | intermediate sheet family |
| `0.3` | 4 | reduced sheet/detail family |
| `0.6` | 1 | isolated sheet scale |
| `0.05` | 1 | very small reference or marker sheet; needs visual check |

The analyzed drawings place sheet inserts in rows across ModelSpace rather than only in paper layouts. Future generated sheets should therefore:

1. Reuse `ZIUM_sheet_architect`.
2. Match one of the existing insert scales unless the user specifies otherwise.
3. Place new drawing geometry inside the sheet's usable drawing area.
4. Preserve the title block as a block insert, not exploded linework.
5. Infer drawing scale from the selected sheet insert scale and intended plotted scale.

## Entity Mix

A 3,031-object uniform sample from an authored office drawing showed this grammar:

| Entity type | Sample count | Reading |
|---|---:|---|
| `LINE` | 1,789 | Primary drafting geometry. |
| `POLYLINE` | 510 | Boundaries, outlines, repeated symbols, hatch-like shapes. |
| `ARC` | 258 | Door swings, fixtures, rounded symbols. |
| `TEXT` | 194 | Most annotation is single-line text. |
| `CIRCLE` | 91 | Symbols, markers, fixtures. |
| `DIMENSION` | 70 | Real dimension entities are used. |
| `INSERT` | 69 | Blocks are important and should be preserved. |
| `HATCH` | 15 | Fills/poche exist but are not dominant. |
| `LEADER` | 11 | Real leader entities are used. |

Future edits should prefer the same entity family:

- Use `LINE`/`POLYLINE` for plan geometry.
- Use real `DIMENSION` entities for dimensions.
- Use real leader entities for callouts.
- Use block inserts where the drawing already uses office symbols or title blocks.
- Avoid exploding existing blocks unless explicitly requested.

## Line Expression

The drawing is mostly ByLayer/ByBlock driven, with color and linetype used heavily as visual grammar.

Observed sample linetypes:

| Linetype | Sample count | Use signal |
|---|---:|---|
| `ByLayer` | 2,366 | dominant; inherit authored layer display |
| `Continuous` | 481 | explicit continuous linework |
| `HIDDEN` | 28 | hidden/overhead/covered geometry |
| `H` | 27 | hidden shorthand; preserve as-is |
| `ByBlock` | 27 | block-dependent symbol display |
| `CEN` | 25 | center/grid/reference lines |
| `DASHED2` | 21 | dashed detail/hidden line family |
| `HIDDENX2` | 15 | scaled hidden line family |
| `HID2` | 11 | hidden line variant |
| `D_HIDDEN` | 8 | hidden/detail variant |

Observed sample colors:

| Color | Sample count | Use signal |
|---:|---:|---|
| `256` | 1,174 | ByLayer color; default for most authored geometry |
| `8` | 958 | major gray construction/fixture/furniture line family |
| `152` | 278 | secondary gray/green-gray family, often arcs/fixtures |
| `4` | 114 | cyan-like CAD color, used for distinct outline/symbol elements |
| `40` | 82 | small repeated object/detail line family |
| `5` | 68 | blue family, often distinct components |
| `7` | 59 | white/title/text family |
| `1` | 42 | red/centerline or emphasis family |
| `3` | 40 | green dimension/detail family |

Observed lineweight use:

| Lineweight | Sample count | Reading |
|---:|---:|---|
| `-1` | 2,812 | ByLayer/ByBlock default; dominant |
| `0` | 216 | explicit 0.00 mm/lightweight lines |
| `-3` | 3 | default/system lineweight; rare |

Editing policy:

- Do not normalize layers during shape edits.
- Preserve ByLayer and ByBlock settings unless a new entity needs explicit visual matching.
- When copying an existing condition, sample nearby entity color/linetype/lineweight and reuse that visual grammar.
- For center/reference lines, use the existing `CEN`/centerline linetype family.
- For hidden lines, preserve the drawing's existing hidden variant rather than introducing a new linetype name.

## Text And Annotation

Observed text heights in the sample include:

| Height | Sample count |
|---:|---:|
| `208.333` | 21 |
| `161.5` | 15 |
| `180.0` | 14 |
| `250.0` | 13 |
| `300.0` | 12 |
| `150.0` | 10 |
| `90.0` | 9 |

This suggests the office drawings use scale-dependent text heights rather than one global modelspace text height. Future text insertion should infer text height from nearby similar annotation or the containing sheet scale.

Dimension and leader rules:

- Keep dimensions as dimension entities.
- Keep leaders as leader entities.
- Do not replace dimensions/leaders with loose linework.
- Generated dimensions should show measured geometry unless the user explicitly asks for a legacy override.
- Generated leaders should use the QLEADER-style landing rule already defined in `docs/17_detail_drafting_standards.md`.

## Future Modification Workflow

When the user asks for a drawing change, use this sequence:

1. Identify the target sheet or region by nearest `ZIUM_sheet_architect` insert.
2. Determine the sheet insert scale and infer working scale.
3. Sample nearby existing geometry for color, linetype, lineweight, text height, and dimension style.
4. Create new geometry using the same visual grammar.
5. Keep existing layers unchanged unless explicitly told otherwise.
6. Use blocks for office sheet/title forms and repeated symbols.
7. Save to a copy first unless the user asks to modify the active DWG directly.

If the user says "도곽까지 같이 생성", the expected behavior is:

1. Insert or reuse `ZIUM_sheet_architect`.
2. Apply a matching title block scale.
3. Place the requested drawing inside the usable sheet area.
4. Generate dimensions, leaders, text, and linework using the local grammar.
5. Leave layer remapping out of scope.

## Open Items

- Need a reliable sheet usable-area measurement from the `ZIUM_sheet_architect` block definition.
- Need a visual screenshot/PDF step to classify sheet titles, drawing names, and scale text.
- Need a handle-level tool to sample style from a selected nearby object before generating new geometry.
