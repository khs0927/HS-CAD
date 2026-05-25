# 39. Text Corrections Export Plan

This document defines PR #16: Text Corrections Export Worker.

## Goal

Create review-friendly CSV exports and correction templates from `TEXT_REVIEW_QUEUE.json`.

This lets a human reviewer inspect uncertain/conflicting text evidence and record corrections in a stable artifact that can be used later for calibration, retraining, or rule refinement.

## Worker

Worker name:

```text
text_corrections_export
```

Command:

```powershell
python -X utf8 -m src.main hscad-worker-run text_corrections_export --workspace outputs\webhard_batch_100
```

## Inputs

```text
TEXT_REVIEW_QUEUE.json
```

Run this first when available:

```powershell
python -X utf8 -m src.main hscad-worker-run text_review_queue --workspace outputs\webhard_batch_100
```

## Outputs

```text
TEXT_REVIEW_QUEUE.csv
TEXT_CORRECTIONS_TEMPLATE.json
TEXT_CORRECTIONS_TEMPLATE.csv
TEXT_CORRECTIONS_EXPORT_REPORT.md
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs/text_corrections_export.jsonl
```

## CSV encoding

CSV files are written with:

```text
utf-8-sig
```

This improves compatibility with Excel on Windows/Korean systems.

## Correction schema

Each correction row includes:

```text
review_rank
target_id
text
corrected_text
correction_status
reviewer_note
confidence
conflict_score
coverage_score
review_reasons
source_pdf
page_index
page_contract_id
pdf_bbox
signals
```

Allowed `correction_status` values:

```text
pending
accepted
corrected
rejected
unclear
```

Usage:

```text
pending   : not reviewed yet
accepted  : original text is correct
corrected : corrected_text is the human-approved value
rejected  : this detection/match should not be used
unclear   : reviewer cannot decide from available evidence
```

## Safety

No source mutation. The worker only reads `TEXT_REVIEW_QUEUE.json` and writes CSV/template artifacts.

## Validation

Run:

```powershell
python -m pytest tests/test_text_corrections_export_worker.py tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run text_corrections_export --workspace outputs\webhard_batch_100
```

Expected files:

```text
outputs\webhard_batch_100\TEXT_REVIEW_QUEUE.csv
outputs\webhard_batch_100\TEXT_CORRECTIONS_TEMPLATE.json
outputs\webhard_batch_100\TEXT_CORRECTIONS_TEMPLATE.csv
outputs\webhard_batch_100\TEXT_CORRECTIONS_EXPORT_REPORT.md
outputs\webhard_batch_100\WORKER_RUNS.json
outputs\webhard_batch_100\WORKER_AUDIT.json
outputs\webhard_batch_100\worker_logs\text_corrections_export.jsonl
```

## Follow-up

Future PRs can add:

```text
TEXT_CORRECTIONS.json importer
text evidence fusion correction overlay
review status persistence
calibration report from corrections
```
