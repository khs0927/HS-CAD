# 41. Text Calibration Report Plan

This document defines PR #18: Text Calibration Report Worker.

## Goal

Analyze human correction outcomes and produce a calibration report for text evidence quality.

This worker helps answer:

```text
Which text evidence items were accepted?
Which were corrected or rejected?
Are high-confidence items still wrong?
Which backend signal should be trusted less or tuned?
```

## Worker

Worker name:

```text
text_calibration_report
```

Command:

```powershell
python -X utf8 -m src.main hscad-worker-run text_calibration_report --workspace outputs\webhard_batch_100
```

## Options

```json
{
  "max_samples_per_status": 5
}
```

## Inputs

```text
TEXT_CORRECTIONS_APPLIED.json
TEXT_EVIDENCE_FUSION_CORRECTED.json
```

Run this first when available:

```powershell
python -X utf8 -m src.main hscad-worker-run text_corrections_apply --workspace outputs\webhard_batch_100
```

## Outputs

```text
TEXT_CALIBRATION_REPORT.json
TEXT_CALIBRATION_REPORT.md
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs/text_calibration_report.jsonl
```

## Metrics

Summary metrics:

```text
applied_count
status_counts
accuracy_proxy
correction_rate
rejection_rate
unclear_rate
```

`accuracy_proxy` is:

```text
accepted_count / applied_count
```

It is not a formal ML accuracy metric. It is a practical calibration proxy from human review results.

## Confidence buckets

The worker groups corrected text evidence by confidence:

```text
0.00-0.25
0.25-0.50
0.50-0.75
0.75-1.00
```

Each bucket includes:

```text
count
accepted
corrected
rejected
unclear
error_like_count
```

`error_like_count` means:

```text
corrected + rejected
```

## Backend signal stats

The worker summarizes available signal contributions:

```text
ocr
vector
cad
```

For each signal group:

```text
count
accepted
corrected
rejected
unclear
avg_score
```

## Samples

The report includes up to `max_samples_per_status` rows for each status:

```text
accepted
corrected
rejected
unclear
```

## Recommendations

The worker emits simple calibration recommendations, for example:

```text
High correction/rejection rate: review OCR/vector/CAD text matching weights before increasing automation.
High-confidence items still contain errors: lower trust thresholds or increase conflict penalty.
Low-confidence bucket has review items: inspect scan quality, OCR language settings, and PDF coordinate alignment.
```

## Safety

No source mutation. The worker only reads correction/evidence artifacts and writes calibration reports.

## Validation

Run:

```powershell
python -m pytest tests/test_text_calibration_report_worker.py tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run text_calibration_report --workspace outputs\webhard_batch_100
```

Expected files:

```text
outputs\webhard_batch_100\TEXT_CALIBRATION_REPORT.json
outputs\webhard_batch_100\TEXT_CALIBRATION_REPORT.md
outputs\webhard_batch_100\WORKER_RUNS.json
outputs\webhard_batch_100\WORKER_AUDIT.json
outputs\webhard_batch_100\worker_logs\text_calibration_report.jsonl
```

## Follow-up

Future PRs can add:

```text
automatic fusion weight suggestions
project/company-specific calibration profiles
layer-aware text role calibration
backend trust score over time
```
