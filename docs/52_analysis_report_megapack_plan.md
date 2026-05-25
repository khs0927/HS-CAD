# 52. Analysis Report Megapack Plan

## Goal

Continue code generation without validation.

This pack adds:

```text
per-file evidence graph partitioning
report redaction plan
dashboard static CSS/JS asset generation
analysis_report_megapack worker
CLI shortcut v3 scaffold
```

## New worker

```text
analysis_report_megapack
```

Expected command:

```powershell
python -X utf8 -m src.main hscad-worker-run analysis_report_megapack --workspace outputs\webhard_batch_100
```

## Outputs

```text
EVIDENCE_GRAPH_PARTITIONS.json
EVIDENCE_GRAPH_PARTITIONS.md
evidence_partitions/*.evidence.json
evidence_partitions/__cross_file_edges__.json
REPORT_REDACTION_PLAN.json
REPORT_REDACTION_PLAN.md
DASHBOARD_STATIC_ASSETS.json
DASHBOARD_STATIC_ASSETS.md
dashboard_assets/hscad_dashboard.css
dashboard_assets/hscad_dashboard.js
```

## Safety

```text
apply_redaction=false by default
source drawings are never touched
only generated artifacts are scanned
```

## Validation TODO

Do not run validation now.

```powershell
python -X utf8 -m src.main hscad-worker-run analysis_report_megapack --workspace outputs\webhard_batch_100
```
