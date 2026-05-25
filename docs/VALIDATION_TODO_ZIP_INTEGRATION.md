# Validation TODO — ZIP Integration

All verification is deferred.

## Later checks

```powershell
git status --short
python -X utf8 -m pytest tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-analysis-run-all-v3 --workspace outputs\webhard_batch_100
```

## Later full worker chain

```powershell
python -X utf8 -m src.main hscad-worker-run analysis_core_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_graph_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_advanced_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_ops_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_automation_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_evidence_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_export_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_storage_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_report_megapack --workspace outputs\webhard_batch_100
```
