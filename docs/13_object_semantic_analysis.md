# Object Semantic Analysis

This layer answers a practical first question for existing DWG drawings:
“What is this line, polyline, block, or text object likely to represent?”

## Priority

1. Layer-based classification is the primary source of truth.
2. Entity type and geometry refine the interpretation.
3. Block names and text content provide additional hints.
4. Screen capture is optional supporting evidence only.

Screen capture must never replace CAD object data when modelspace objects are
available. Capture failures are warnings, not analysis failures.

## User Layer Standard

- `COL`: Structural members, including concrete columns, concrete walls, steel walls, and steel beams.
- `WAL1`: Non-structural wall, gray lightweight wall.
- `WAL2`: Non-structural wall, green masonry wall.
- `WAL3`: Other non-structural wall.
- `ELE`, `ELE1` to `ELE4`: Elevation linework with colors 8, 251, 252, 253, 254.
- `ETC`, `ETC1` to `ETC4`: Other linework following the ELE color rules.
- `DOOR`, `DOOR_ELE`: Door plan and door elevation objects.
- `WIN`, `WINBAR`, `WINELE`: Window plan, frame/bar, and elevation objects.
- `STAIR`: Stair objects.
- `DIM`, `DIMLE`: Dimensions and leaders.
- `CEN`, `CEN1`, `CEN2`: Main and auxiliary centerlines.
- `DEFPOINTS`: Non-plot guide layer.
- `FIX`, `FUR`: Built-in fixtures and furniture.
- `SYM`, `SYM_T`: Symbols and symbol text.
- `TIT`: Title and drawing text.
- `AREA`: Site or cadastral boundary line.
- `PARKING`: Parking linework.
- `INS`: Insulation.
- `BOUND`: Zone or area boundary.
- `A-FORM`: Drawing border or form.
- `MARK`: Shared coordination mark.

## CLI

```powershell
python -m src.main layer-taxonomy
python -m src.main classify-objects --dwg "C:/cad/sample.dwg" --out "outputs/object_semantics.json"
python -m src.main analyze-architecture --dwg "C:/cad/sample.dwg" --out-dir "outputs/architecture_report"
python -m src.main capture-screen --out "outputs/zwcad_screen.png"
```

## Report Outputs

`analyze-architecture` includes:

- `object_semantics.json`
- `semantic_summary.json`
- `object_semantics.xlsx`
- `layer_semantics.xlsx`
- `drawing_semantic_summary.md`

Each classified object includes `analysis_order` and `evidence` so reviewers can
see whether the conclusion came from the layer rule, geometry, block name, text,
or only supporting visual context.
