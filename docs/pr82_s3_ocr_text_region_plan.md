# PR82-S3 OCR Text Region Extraction Plan

This PR is the first narrow extraction from the PR82 OCR Tools group.

## Scope

Included:

```text
src/ocr/__init__.py
src/ocr/text_region_analysis.py
src/workers/ocr_text_region_worker.py
tests/test_ocr_text_region_worker.py
```

Excluded:

```text
src/main.py
config/worker_manifest.json
outputs/**
artifacts/**/*.zip
live CAD execution
```

## Safety

This extraction is review-only. It discovers rendered images, optionally runs PaddleOCR if installed, writes JSON/Markdown OCR region artifacts into a workspace, and returns worker metrics.

It does not mutate DWG/DXF files, does not call ZWCAD COM, does not call SendCommand, does not call SaveAs, and does not execute XiCAD aliases.

## Expected validation

```powershell
python -X utf8 -m pytest -q tests/test_ocr_text_region_worker.py
python -X utf8 -m compileall -q src/ocr src/workers tests
```

## Next OCR extraction candidates

After this PR is validated, continue with smaller PRs for:

```text
src/ocr/vector_text_matching.py
src/ocr/cad_text_matching.py
src/ocr/text_evidence_fusion.py
src/ocr/text_review_queue.py
src/ocr/text_corrections_export.py
src/ocr/text_corrections_apply.py
src/ocr/text_calibration_report.py
src/ocr/text_weight_suggestions.py
```

Keep CLI registration and worker manifest registration as candidate docs only until each OCR module is validated.
