# 36. OCR ↔ CAD TEXT/MTEXT Match Plan

This document defines PR #13: OCR to CAD TEXT/MTEXT Match Worker.

## Goal

Connect the PDF/OCR analysis layer with the CAD/DXF fileized layer.

This worker compares:

```text
OCR_TEXT_REGIONS.json
fileized/json/*.json CAD TEXT / MTEXT entities
```

The result becomes an evidence bridge between raster/OCR/PDF analysis and original CAD vector text.

## Worker

Worker name:

```text
ocr_cad_text_match
```

Command:

```powershell
python -X utf8 -m src.main hscad-worker-run ocr_cad_text_match --workspace outputs\webhard_batch_100
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
fileized/json/*.json
```

Run these first when available:

```powershell
python -X utf8 -m src.main hscad-worker-run pdf_raster --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run ocr_text_region --workspace outputs\webhard_batch_100
```

For CAD text, run the fileize pipeline first so `fileized/json/*.json` exists.

## Outputs

```text
OCR_CAD_TEXT_MATCHES.json
OCR_CAD_TEXT_MATCH_REPORT.md
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs/ocr_cad_text_match.jsonl
```

## Matching logic

CAD model coordinates and PDF page coordinates often differ. Therefore the initial matching strategy uses:

```text
80% normalized text similarity
20% optional bbox IoU
```

BBox IoU only contributes when both OCR and CAD artifacts already expose comparable 4-value bbox fields.

The score is intentionally simple and explainable. It is evidence, not final semantic truth.

## OCR_CAD_TEXT_MATCHES.json

Summary fields:

```text
ocr_region_count
cad_text_count
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
ocr_source_pdf
ocr_page_index
ocr_page_contract_id
ocr_pdf_bbox
cad_index
cad_text
cad_file_id
cad_relative_path
cad_handle
cad_entity_type
cad_layer
cad_bbox
text_similarity
bbox_iou
match_score
```

## Safety

No source mutation. The worker only reads OCR/fileized JSON artifacts and writes derived match reports.

## Validation

Run:

```powershell
python -m pytest tests/test_ocr_cad_text_match_worker.py tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run ocr_cad_text_match --workspace outputs\webhard_batch_100
```

Expected files:

```text
outputs\webhard_batch_100\OCR_CAD_TEXT_MATCHES.json
outputs\webhard_batch_100\OCR_CAD_TEXT_MATCH_REPORT.md
outputs\webhard_batch_100\WORKER_RUNS.json
outputs\webhard_batch_100\WORKER_AUDIT.json
outputs\webhard_batch_100\worker_logs\ocr_cad_text_match.jsonl
```

## Follow-up

Future PRs can add:

```text
CAD TEXT ↔ PDF vector text matching
text evidence fusion score
text conflict review queue
layer-aware text role inference
```
