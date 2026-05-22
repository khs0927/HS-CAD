# 21. HS-CAD Corpus Foundation

This branch adds the first safe foundation for the HS-CAD corpus workflow.

## Goal

The first milestone is not large-scale batch processing. The first milestone is a stable record schema and a staged workflow that can be tested before running on a whole workspace.

## New commands

```powershell
python -m src.main corpus-run prepare --root "C:/cad/source" --workspace "outputs/corpus_workspace" --sample 20
python -m src.main corpus-run fileize --workspace "outputs/corpus_workspace" --limit 20
python -m src.main corpus-run index --workspace "outputs/corpus_workspace"
python -m src.main corpus-run query "glasswool panel" --workspace "outputs/corpus_workspace"
python -m src.main corpus-run report --workspace "outputs/corpus_workspace"
```

## New packages

- `src/corpus/schema.py`: stable `FileizedDrawingRecord` shape.
- `src/fileizers/base.py`: fileizer interface and JSON/Markdown writer.
- `src/fileizers/dwg_zwcad_fileizer.py`: DWG fileizer using the existing ZWCAD COM adapter.
- `src/fileizers/dxf_ezdxf_fileizer.py`: DXF fileizer for CI-friendly validation.
- `src/corpus/indexer.py`: SQLite indexer with `files`, `layers`, `entities`, `texts`, `blocks`, `dimensions`, and `failures` tables.
- `src/corpus/query.py`: basic FTS/LIKE text evidence search.
- `src/corpus/report_builder.py`: `FINAL_REPORT.md` summary builder.
- `src/corpus_run/manifest.py`: source folder scanner and manifest writer.
- `src/corpus_run/pipeline_runner.py`: staged prepare/fileize/index/query/report runner.
- `src/app/corpus_cli.py`: Typer CLI registration under `corpus-run`.

## Safety rules

- Run `prepare` with `--sample` first.
- Run `fileize` with `--limit` first.
- DWG fileization uses ZWCAD COM and may report `unavailable` on machines without ZWCAD or COM.
- DXF fileization is included so pytest can validate the corpus flow without ZWCAD.
- This foundation does not mutate drawings.

## Test

```powershell
python -m pytest tests/test_corpus_foundation.py
python -m src.main corpus-run prepare --root "C:/cad/source" --workspace "outputs/corpus_workspace" --sample 5
```
