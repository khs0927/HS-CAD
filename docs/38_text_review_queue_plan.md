# 38. Text Review Queue Plan

This document defines PR #15: Text Review Queue Worker.

## Goal

Create a human review queue from `TEXT_EVIDENCE_FUSION.json`.

The worker extracts only text evidence items that require review, then sorts them so a reviewer can inspect the most risky text evidence first.

## Worker

Worker name:

```text
text_review_queue
```

Command:

```powershell
python -X utf8 -m src.main hscad-worker-run text_review_queue --workspace outputs\webhard_batch_100
```

## Options

```json
{
  "include_all": false
}
```

## Inputs

```text
TEXT_EVIDENCE_FUSION.json
```

Run this first when available:

```powershell
python -X utf8 -m src.main hscad-worker-run text_evidence_fusion --workspace outputs\webhard_batch_100
```

## Outputs

```text
TEXT_REVIEW_QUEUE.json
TEXT_REVIEW_QUEUE.md
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs/text_review_queue.jsonl
```

## Queue policy

The queue includes items where:

```text
review_required == true
```

Sorting priority:

```text
1. Higher conflict_score first
2. Lower confidence first
```

Review reasons:

```text
low_confidence
text_conflict
low_evidence_coverage
review_required
```

## TEXT_REVIEW_QUEUE.json

Summary fields:

```text
source_item_count
queue_count
high_conflict_count
low_confidence_count
```

Item fields:

```text
review_rank
target_id
text
source_pdf
page_index
page_contract_id
pdf_bbox
confidence
conflict_score
coverage_score
review_required
review_reasons
signals
```

## TEXT_REVIEW_QUEUE.md

Markdown summary with a table:

```text
Rank | Text | Confidence | Conflict | Reasons | Source
```

## Safety

No source mutation. The worker only reads `TEXT_EVIDENCE_FUSION.json` and writes review queue artifacts.

## Validation

Run:

```powershell
python -m pytest tests/test_text_review_queue_worker.py tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run text_review_queue --workspace outputs\webhard_batch_100
```

Expected files:

```text
outputs\webhard_batch_100\TEXT_REVIEW_QUEUE.json
outputs\webhard_batch_100\TEXT_REVIEW_QUEUE.md
outputs\webhard_batch_100\WORKER_RUNS.json
outputs\webhard_batch_100\WORKER_AUDIT.json
outputs\webhard_batch_100\worker_logs\text_review_queue.jsonl
```

## Follow-up

Future PRs can add:

```text
review queue CSV export
review status persistence
human correction artifact
layer-aware text role inference
```
