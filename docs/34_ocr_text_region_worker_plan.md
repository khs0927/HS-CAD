# 34. OCR Text Region Worker Plan

This document defines PR #11: optional OCR Text Region Worker.

## Goal

Add an OCR worker that places OCR text boxes into the same coordinate contract created by the PDF/Raster worker.

This prepares cross-validation between:

```text
CAD TEXT / MTEXT
PDF vector chars
OCR text regions
Raster contour candidates
```

## Worker

Worker name:

```text
ocr_text_region
```

Command:

```powershell
python -X utf8 -m src.main hscad-worker-run ocr_text_region --workspace outputs\webhard_batch_100
```

## Options

```json
{
  "max_images": 20,
  "language": "korean"
}
```

## Inputs

The worker reads rendered images and coordinate contract artifacts from the workspace:

```text
pdf_raster/rendered/*.png
PDF_COORDINATE_CONTRACT.json
```

If rendered images are missing, run the PDF/Raster worker first:

```powershell
python -X utf8 -m src.main hscad-worker-run pdf_raster --workspace outputs\webhard_batch_100
```

## Backend

Initial backend:

```text
PaddleOCR
```

PaddleOCR is optional. If it is missing, the worker records warnings and still writes stable empty artifacts.

## Outputs

```text
OCR_REGION_ANALYSIS.json
OCR_TEXT_REGIONS.json
OCR_REGION_REPORT.md
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs/ocr_text_region.jsonl
```

## OCR_TEXT_REGIONS.json

Each OCR region includes:

```text
source_image
source_pdf
page_index
page_contract_id
line_index
text
confidence
pixel_bbox
pdf_bbox
normalized_bbox
coordinate_space
points
```

When `PDF_COORDINATE_CONTRACT.json` is available, OCR pixel bbox is converted into PDF-space bbox and normalized bbox.

## Safety

The worker only reads source images and writes derived OCR artifacts. It does not modify CAD/PDF/image sources.

## Validation

Run:

```powershell
python -m pytest tests/test_ocr_text_region_worker.py tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run ocr_text_region --workspace outputs\webhard_batch_100
```

Expected files:

```text
outputs\webhard_batch_100\OCR_REGION_ANALYSIS.json
outputs\webhard_batch_100\OCR_TEXT_REGIONS.json
outputs\webhard_batch_100\OCR_REGION_REPORT.md
outputs\webhard_batch_100\WORKER_RUNS.json
outputs\webhard_batch_100\WORKER_AUDIT.json
outputs\webhard_batch_100\worker_logs\ocr_text_region.jsonl
```

## Follow-up

Future PRs can add:

```text
docTR fallback
OCR ↔ PDF vector text matching
OCR ↔ CAD TEXT/MTEXT matching
OCR ↔ contour text_blob_candidate matching
layout/table/titleblock detection
```
