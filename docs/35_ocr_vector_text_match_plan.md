# 35. OCR ↔ PDF Vector Text Match Plan

This document defines PR #12: OCR to PDF Vector Text Match Worker.

## Goal

Compare OCR text regions with pdfplumber vector text objects in the same PDF coordinate space.

This prepares evidence fusion between:

```text
OCR_TEXT_REGIONS.json
PDF_VECTOR_OBJECTS.json
CAD TEXT / MTEXT
text_blob_candidate contours
```

## Worker

Worker name:

```text
ocr_vector_text_match
```

Command:

```powershell
python -X utf8 -m src.main hscad-worker-run ocr_vector_text_match --workspace outputs\webhard_batch_100
```

## Options

```json
{
  "min_score": 0.15
}
```

## Inputs

```text
OCR_TEXT_REGIONS.json
PDF_VECTOR_OBJECTS.json
```

Run these first:

```powershell
python -X utf8 -m src.main hscad-worker-run pdf_raster --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run ocr_text_region --workspace outputs\webhard_batch_100
```

## Outputs

```text
OCR_VECTOR_TEXT_MATCHES.json
OCR_VECTOR_TEXT_MATCH_REPORT.md
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs/ocr_vector_text_match.jsonl
```

## Matching logic

Candidate matching is restricted to the same:

```text
source_pdf
page_index
page_contract_id
```

Each candidate score combines:

```text
65% bbox IoU
35% normalized text similarity
```

The initial score is intentionally simple and explainable. It is evidence, not final truth.

## OCR_VECTOR_TEXT_MATCHES.json

Summary fields:

```text
ocr_region_count
vector_text_count
match_count
unmatched_ocr_count
avg_match_score
avg_text_similarity
avg_bbox_iou
```

Match fields:

```text
ocr_index
ocr_text
ocr_confidence
vector_text
source_pdf
page_index
page_contract_id
ocr_pdf_bbox
vector_pdf_bbox
bbox_iou
text_similarity
match_score
vector_object_type
vector_index_on_page
```

## Safety

No source mutation. The worker only reads artifacts and writes derived match reports.

## Validation

Run:

```powershell
python -m pytest tests/test_ocr_vector_text_match_worker.py tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run ocr_vector_text_match --workspace outputs\webhard_batch_100
```

Expected files:

```text
outputs\webhard_batch_100\OCR_VECTOR_TEXT_MATCHES.json
outputs\webhard_batch_100\OCR_VECTOR_TEXT_MATCH_REPORT.md
outputs\webhard_batch_100\WORKER_RUNS.json
outputs\webhard_batch_100\WORKER_AUDIT.json
outputs\webhard_batch_100\worker_logs\ocr_vector_text_match.jsonl
```

## Follow-up

Future PRs can add:

```text
OCR ↔ CAD TEXT/MTEXT matching
OCR ↔ text_blob_candidate contour matching
text evidence fusion score
review queue for conflicting text evidence
```
