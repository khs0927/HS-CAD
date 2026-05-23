# 37. Text Evidence Fusion Plan

This document defines PR #14: Text Evidence Fusion Worker.

## Goal

Combine OCR, PDF vector text, and CAD TEXT/MTEXT match evidence into one explainable confidence score.

This worker consumes:

```text
OCR_TEXT_REGIONS.json
OCR_VECTOR_TEXT_MATCHES.json
OCR_CAD_TEXT_MATCHES.json
```

and writes:

```text
TEXT_EVIDENCE_FUSION.json
TEXT_EVIDENCE_FUSION_REPORT.md
```

## Worker

Worker name:

```text
text_evidence_fusion
```

Command:

```powershell
python -X utf8 -m src.main hscad-worker-run text_evidence_fusion --workspace outputs\webhard_batch_100
```

## Options

```json
{
  "review_threshold": 0.55,
  "conflict_threshold": 0.35
}
```

## Inputs

Run these first when available:

```powershell
python -X utf8 -m src.main hscad-worker-run pdf_raster --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run ocr_text_region --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run ocr_vector_text_match --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run ocr_cad_text_match --workspace outputs\webhard_batch_100
```

Required artifacts:

```text
OCR_TEXT_REGIONS.json
OCR_VECTOR_TEXT_MATCHES.json
OCR_CAD_TEXT_MATCHES.json
```

Missing files are allowed. They result in lower coverage/confidence rather than fatal failure.

## Outputs

```text
TEXT_EVIDENCE_FUSION.json
TEXT_EVIDENCE_FUSION_REPORT.md
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs/text_evidence_fusion.jsonl
```

## Scoring policy v1

The initial policy is intentionally simple and explainable:

```text
45% OCR confidence
30% OCR ↔ PDF vector text match score
20% OCR ↔ CAD TEXT/MTEXT match score
 5% coverage bonus
25% conflict penalty
```

Confidence formula:

```text
confidence = clamp(
  0.45 * ocr_confidence
+ 0.30 * vector_match_score
+ 0.20 * cad_match_score
+ 0.05 * coverage_score
- 0.25 * conflict_score
)
```

Review rule:

```text
review_required = confidence < review_threshold OR conflict_score >= conflict_threshold
```

## Conflict score

Conflict is computed from disagreement among available text values:

```text
OCR text
PDF vector text
CAD text
```

This is not final semantic truth. It is an audit signal for human review.

## TEXT_EVIDENCE_FUSION.json

Summary fields:

```text
item_count
review_required_count
conflict_count
avg_confidence
```

Item fields:

```text
target_id
text
source_pdf
page_index
page_contract_id
pdf_bbox
confidence
review_required
conflict_score
coverage_score
signals
```

Signals include:

```text
ocr_confidence
ocr_text
vector_match_score
vector_text
vector_match_ref
cad_match_score
cad_text
cad_match_ref
```

## Safety

No source mutation. The worker only reads derived artifacts and writes fusion reports.

## Validation

Run:

```powershell
python -m pytest tests/test_text_evidence_fusion_worker.py tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run text_evidence_fusion --workspace outputs\webhard_batch_100
```

Expected files:

```text
outputs\webhard_batch_100\TEXT_EVIDENCE_FUSION.json
outputs\webhard_batch_100\TEXT_EVIDENCE_FUSION_REPORT.md
outputs\webhard_batch_100\WORKER_RUNS.json
outputs\webhard_batch_100\WORKER_AUDIT.json
outputs\webhard_batch_100\worker_logs\text_evidence_fusion.jsonl
```

## Follow-up

Future PRs can add:

```text
review queue artifact
layer-aware text role inference
CAD TEXT ↔ PDF vector text direct matching
Dempster-Shafer text evidence fusion
```
