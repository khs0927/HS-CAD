# 40. Text Corrections Apply Plan

This document defines PR #17: Text Corrections Apply Worker.

## Goal

Read human correction artifacts and overlay them onto `TEXT_EVIDENCE_FUSION.json`.

This creates a corrected, human-aware text evidence artifact that downstream calibration or reporting can use.

## Worker

Worker name:

```text
text_corrections_apply
```

Command:

```powershell
python -X utf8 -m src.main hscad-worker-run text_corrections_apply --workspace outputs\webhard_batch_100
```

## Inputs

The worker looks for corrections in this priority order:

```text
TEXT_CORRECTIONS.json
TEXT_CORRECTIONS_TEMPLATE.json
TEXT_CORRECTIONS.csv
TEXT_CORRECTIONS_TEMPLATE.csv
```

Main evidence input:

```text
TEXT_EVIDENCE_FUSION.json
```

Run this first when available:

```powershell
python -X utf8 -m src.main hscad-worker-run text_corrections_export --workspace outputs\webhard_batch_100
```

Then a human reviewer can edit the generated template/csv and rerun this worker.

## Outputs

```text
TEXT_CORRECTIONS_APPLIED.json
TEXT_EVIDENCE_FUSION_CORRECTED.json
TEXT_CORRECTIONS_APPLY_REPORT.md
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs/text_corrections_apply.jsonl
```

## Correction status handling

```text
pending   -> ignored
accepted  -> final_text = original text, usable = true, human_verified = true
corrected -> final_text = corrected_text, usable = true, human_verified = true
rejected  -> usable = false, human_verified = true
unclear   -> usable = false, human_verified = false
```

## Corrected item fields

Each item in `TEXT_EVIDENCE_FUSION_CORRECTED.json` receives defaults:

```text
final_text
usable
human_verified
correction_applied
```

When a correction is applied, it also receives:

```text
correction_status
correction_note
```

## TEXT_CORRECTIONS_APPLIED.json

Summary fields:

```text
source_item_count
correction_count
applied_count
accepted_count
corrected_count
rejected_count
unclear_count
```

Applied row fields:

```text
target_id
before_text
final_text
correction_status
usable
human_verified
reviewer_note
```

## Safety

No source mutation. The worker only reads correction/evidence artifacts and writes corrected derivative artifacts.

## Validation

Run:

```powershell
python -m pytest tests/test_text_corrections_apply_worker.py tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run text_corrections_apply --workspace outputs\webhard_batch_100
```

Expected files:

```text
outputs\webhard_batch_100\TEXT_CORRECTIONS_APPLIED.json
outputs\webhard_batch_100\TEXT_EVIDENCE_FUSION_CORRECTED.json
outputs\webhard_batch_100\TEXT_CORRECTIONS_APPLY_REPORT.md
outputs\webhard_batch_100\WORKER_RUNS.json
outputs\webhard_batch_100\WORKER_AUDIT.json
outputs\webhard_batch_100\worker_logs\text_corrections_apply.jsonl
```

## Follow-up

Future PRs can add:

```text
calibration report from corrections
rule/weight tuning from accepted/corrected/rejected rows
layer-aware text role inference using corrected labels
```
