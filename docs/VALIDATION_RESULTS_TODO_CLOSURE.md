# HS-CAD TODO Closure Validation

## 1. Validation Date / Environment

- Date: 2026-05-24 KST
- OS: Windows 11
- Shell: PowerShell with `chcp 65001` and `PYTHONIOENCODING=utf-8`
- Python: 3.12.4
- Workspace used: `outputs\webhard_batch_100`
- Additional sample workspace: `outputs\webhard_validation_check`

## 2. Branch / Commit

- Branch: `pr-25-analysis-graph-megapack`
- Current commit during final validation: `0b58cc4651bd0916ee550a16cac3572546d3049a`
- PR #25 fetched head: `21667d3df6b6024c6b36bea52470d939e3f58d61`
- Note: the local branch is a descendant of the fetched PR #25 head. The validation patches were applied on this branch after confirming the PR #25 head ancestry.

## 3. Installed Packages

- Installed from `requirements.txt`
- Installed/confirmed optional packages: `pytest`, `shapely`, `networkx`, `duckdb`, `pandas`, `pyarrow`, `polars`, `pymupdf`, `pdfplumber`, `opencv-python-headless`, `numpy`
- `paddleocr` was not installed; `ocr_text_region` handled this gracefully with warnings.

## 4. Commands Run

```powershell
git fetch origin pull/25/head
git switch pr-25-analysis-graph-megapack
python --version
python -X utf8 -m pip install -U pip
python -X utf8 -m pip install -r requirements.txt
python -X utf8 -m pip install pytest shapely networkx duckdb pandas pyarrow polars pymupdf pdfplumber opencv-python-headless numpy
python -X utf8 -m pytest -q
python -X utf8 -m src.main hscad-webhard-sample --drive "Z:/" --workspace "outputs\webhard_validation_check" --sample 5 --limit 5
python -X utf8 -m src.main hscad-worker-run pdf_raster --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run ocr_text_region --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run ocr_vector_text_match --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run ocr_cad_text_match --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run text_evidence_fusion --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run text_review_queue --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run text_corrections_export --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run text_corrections_apply --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run text_calibration_report --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run text_weight_suggestions --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_core_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_graph_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run duckdb_export --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run networkx_graph_audit --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run shapely_topology --workspace outputs\webhard_batch_100
```

## 5. Tests

- Final result: `282 passed, 16 skipped`
- Log: `outputs\pytest_full_exact_pr25_with_fixes.log`
- Earlier failures fixed:
  - ZWCAD/XiCAD adapter circular imports through `src.app`
  - DuckDB list registration incompatibility with current DuckDB
  - layer semantic matching after dash-to-underscore normalization
  - text role priority where leader/text layer hints overrode room/table/spec roles
  - PDF raster IoU match missing `contour_class`
  - text weight rounding drift (`0.950001` vs `0.95`)
  - planned worker test expecting `duckdb_export` unavailable even though it is implemented

## 6. Artifacts

- `outputs\webhard_validation_check\webhard_sample_run.json`
- `outputs\webhard_validation_check\QUALITY_AUDIT.md`
- `outputs\webhard_validation_check\FINAL_REPORT.md`
- `outputs\webhard_validation_check\tmp\dxf\<file_id>\*.dwg`
- `outputs\webhard_validation_check\tmp\dxf\<file_id>\*.dxf`
- `outputs\webhard_batch_100\PDF_RASTER_ANALYSIS.json`
- `outputs\webhard_batch_100\OCR_REGION_ANALYSIS.json`
- `outputs\webhard_batch_100\TEXT_EVIDENCE_FUSION.json`
- `outputs\webhard_batch_100\TEXT_REVIEW_QUEUE.json`
- `outputs\webhard_batch_100\TEXT_CORRECTIONS_TEMPLATE.json`
- `outputs\webhard_batch_100\TEXT_CORRECTIONS_APPLIED.json`
- `outputs\webhard_batch_100\TEXT_CALIBRATION_REPORT.json`
- `outputs\webhard_batch_100\TEXT_FUSION_WEIGHT_SUGGESTIONS.json`
- `outputs\webhard_batch_100\TEXT_ROLE_INFERENCE.json`
- `outputs\webhard_batch_100\GEOMETRY_LOOP_BUILDER.json`
- `outputs\webhard_batch_100\LEADER_GRAPH.json`
- `outputs\webhard_batch_100\DIMENSION_GRAPH.json`
- `outputs\webhard_batch_100\TABLE_GRID_DETECTOR.json`
- `outputs\webhard_batch_100\TITLEBLOCK_CLASSIFIER.json`
- `outputs\webhard_batch_100\DUCKDB_EXPORT.json`
- `outputs\webhard_batch_100\GRAPH_AUDIT.json`
- `outputs\webhard_batch_100\SHAPELY_TOPOLOGY.json`

## 7. Worker Summary

| Worker | Status | Key metrics / notes |
|---|---|---|
| `pdf_raster` | ok | no PDFs discovered in current batch workspace; dependencies available |
| `ocr_text_region` | ok | no rendered images; `paddleocr unavailable` warning, graceful |
| `ocr_vector_text_match` | ok | 0 OCR regions, 0 matches |
| `ocr_cad_text_match` | ok | 115831 CAD text rows, 0 OCR matches |
| `text_evidence_fusion` | ok | policy source `TEXT_FUSION_WEIGHT_SUGGESTIONS.json`, 0 items |
| `text_review_queue` | ok | 0 queue items |
| `text_corrections_export` | ok | 0 queue items, template generated |
| `text_corrections_apply` | ok | 1 mock correction tested, target not found warning |
| `text_calibration_report` | ok | no applied corrections warning |
| `text_weight_suggestions` | ok | default weights suggested due no calibration data |
| `analysis_core_megapack` | warning | scaffold warning; text roles 115834, areas 63916, dimensions 74999 |
| `analysis_graph_megapack` | warning | scaffold warning; closed candidates 44283, fragment groups 164836 |
| `duckdb_export` | ok | files 100, entities 468685, texts 115834 |
| `networkx_graph_audit` | ok | graph has 0 nodes/edges in current artifacts |
| `shapely_topology` | ok | topology polygons 471143, audit findings 135 |

## 8. Failures Summary

- `outputs\webhard_batch_100\failures`: 0 JSON failures found.
- `outputs\webhard_validation_check\failures`: 0 JSON failures found.
- Webhard sample created 5 fileized JSON records: 3 DWG via `zwcad_saveas_dxf_ezdxf`, 2 PDF via `pymupdf`.
- DWG conversion produced staged DWG and DXF files under nested `tmp\dxf\<file_id>` directories.
- ODA usage is recorded under `metadata.external_converter_used: true` and warning type `external_converter_used`.

## 9. Modified Files

- `src/adapters/zwcad_com_adapter.py`
- `src/adapters/xicad_adapter.py`
- `src/analysis/leader_graph_builder.py`
- `src/analysis/dimension_graph_builder.py`
- `src/analysis/layer_semantics.py`
- `src/analytics/duckdb_export.py`
- `src/ocr/policy_loader.py`
- `src/ocr/text_evidence_fusion.py`
- `src/ocr/text_weight_suggestions.py`
- `src/pdf_raster/pdf_raster_analysis.py`
- `src/spatial/text_roles.py`
- `src/workers/text_evidence_fusion_worker.py`
- `tests/test_text_evidence_fusion_worker.py`
- `tests/test_worker_runner.py`

## 10. Remaining TODO

- Install and validate `paddleocr` in a dedicated OCR environment.
- Add real correction samples so calibration and weight suggestions can move away from defaults.
- Continue real Shapely `polygonize_full` implementation for `REAL_GEOMETRY_POLYGONIZER.json`.
- Add reusable bbox/STRtree spatial index service for candidate pruning.
- Promote table grid scaffold to real table cell extraction.
- Add titleblock key-value extraction.
- Add layer profile sampler before defining company-specific mappings.
- Add top-level provenance to Markdown/CSV artifacts or relax audit rules for non-JSON artifacts.

## 11. Recommended Next Order

1. Run OCR with PaddleOCR installed and regenerate text evidence.
2. Apply a small human correction file and rerun calibration + weight suggestions.
3. Build `real_geometry_polygonizer` with Shapely `polygonize_full`.
4. Add spatial index service and use it in containment/leader/dimension/table workers.
5. Implement table cell extraction.
6. Implement titleblock key-value extraction.
7. Implement layer profile sampler.
