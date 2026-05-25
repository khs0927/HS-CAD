# Validation TODO — Report Megapack

All verification is deferred.

## Commands

```powershell
python -X utf8 -m pytest tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run analysis_report_megapack --workspace outputs\webhard_batch_100
```

## Expected artifacts

```text
EVIDENCE_GRAPH_PARTITIONS.json
REPORT_REDACTION_PLAN.json
DASHBOARD_STATIC_ASSETS.json
dashboard_assets/hscad_dashboard.css
dashboard_assets/hscad_dashboard.js
```
