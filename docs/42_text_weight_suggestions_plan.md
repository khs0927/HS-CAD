# 42. Text Fusion Weight Suggestions Plan

This document defines PR #19: Text Fusion Weight Suggestions Worker.

## Goal

Generate project-specific text evidence fusion weight suggestions from `TEXT_CALIBRATION_REPORT.json`.

This worker does not automatically override production policy. It creates a proposal artifact that can be reviewed and applied later.

## Worker

Worker name:

```text
text_weight_suggestions
```

Command:

```powershell
python -X utf8 -m src.main hscad-worker-run text_weight_suggestions --workspace outputs\webhard_batch_100
```

## Inputs

```text
TEXT_CALIBRATION_REPORT.json
```

Run this first when available:

```powershell
python -X utf8 -m src.main hscad-worker-run text_calibration_report --workspace outputs\webhard_batch_100
```

## Outputs

```text
TEXT_FUSION_WEIGHT_SUGGESTIONS.json
TEXT_FUSION_WEIGHT_SUGGESTIONS.md
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs/text_weight_suggestions.jsonl
```

## Default policy

Default text evidence fusion weights:

```text
ocr_confidence   0.45
vector_match     0.30
cad_match        0.20
coverage         0.05
conflict_penalty 0.25
```

The worker only adjusts the core evidence weights:

```text
ocr_confidence
vector_match
cad_match
```

Then it renormalizes them so the core sum remains:

```text
0.95
```

`coverage` remains `0.05`.

`conflict_penalty` may be raised when correction/rejection rates or high-confidence errors are high.

## Backend reliability

For each backend signal group:

```text
ocr
vector
cad
```

The worker reads:

```text
count
accepted
corrected
rejected
unclear
avg_score
```

It estimates:

```text
accepted_ratio
error_like_ratio
unclear_ratio
reliability_score
weight_multiplier
```

`error_like_ratio` means:

```text
(corrected + rejected) / count
```

## Suggested output

`TEXT_FUSION_WEIGHT_SUGGESTIONS.json` includes:

```text
summary
default_weights
suggested_weights
backend_reliability
policy_patch
warnings
provenance
```

The `policy_patch` block is intentionally explicit:

```json
{
  "text_evidence_fusion": {
    "weights": {
      "ocr_confidence": 0.45,
      "vector_match": 0.30,
      "cad_match": 0.20,
      "coverage": 0.05,
      "conflict_penalty": 0.25
    },
    "notes": "Generated from human correction calibration. Treat as a proposal, not an automatic production override."
  }
}
```

## Safety

No source mutation. The worker only reads calibration artifacts and writes weight suggestion reports.

## Validation

Run:

```powershell
python -m pytest tests/test_text_weight_suggestions_worker.py tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run text_weight_suggestions --workspace outputs\webhard_batch_100
```

Expected files:

```text
outputs\webhard_batch_100\TEXT_FUSION_WEIGHT_SUGGESTIONS.json
outputs\webhard_batch_100\TEXT_FUSION_WEIGHT_SUGGESTIONS.md
outputs\webhard_batch_100\WORKER_RUNS.json
outputs\webhard_batch_100\WORKER_AUDIT.json
outputs\webhard_batch_100\worker_logs\text_weight_suggestions.jsonl
```

## Follow-up

Future PRs can add:

```text
project/company-specific calibration profiles
policy patch importer
text_evidence_fusion custom policy loading
layer-aware text role calibration
```
