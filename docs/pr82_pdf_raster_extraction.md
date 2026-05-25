# PR82 PDF Raster Extraction

## Purpose

This PR extracts only the PDF Raster group from draft PR82.

## Included

- `src/pdf_raster/__init__.py`
- `src/pdf_raster/pdf_raster_analysis.py`
- `src/pdf_raster/contour_classification.py`
- `src/workers/pdf_raster_worker.py`
- `tests/test_pdf_raster_worker.py`

## Excluded

- `src/main.py`
- `config/worker_manifest.json`
- `outputs/**`
- `artifacts/**/*.zip`
- binary/runtime artifacts
- generated reports from PR82

## Worker manifest policy

This extraction does not edit `config/worker_manifest.json` directly.

Worker registration should be reviewed later as a separate candidate patch after this source group is validated.

Candidate worker entry:

```json
{
  "pdf_raster": {
    "path": "src.workers.pdf_raster_worker",
    "description": "PDF raster/vector review worker"
  }
}
```

## Expected focused tests

```powershell
python -X utf8 -m pytest -q tests/test_pdf_raster_worker.py
python -X utf8 -m compileall -q src/pdf_raster src/workers tests
```

## Safety

The worker writes derived review artifacts into a caller-provided workspace. It does not modify original CAD files and does not register itself globally in this PR.
