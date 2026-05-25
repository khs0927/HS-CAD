# Validation TODO — Export Megapack

All verification is deferred.

## TODO commands

```powershell
git switch local-megapack-final

python -m pip install -r requirements.txt
python -m pip install pytest shapely

python -X utf8 -m pytest tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q

python -X utf8 -m src.main hscad-worker-run analysis_core_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_graph_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_advanced_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_ops_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_automation_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_evidence_megapack --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-worker-run analysis_export_megapack --workspace outputs\webhard_batch_100
```

## Expected artifacts

```text
VALIDATION_THRESHOLDS.json
VALIDATION_THRESHOLD_CONFIG.json
EVIDENCE_GRAPH_EXPORT.json
evidence_graph/nodes.jsonl
evidence_graph/edges.jsonl
evidence_graph/nodes.csv
evidence_graph/edges.csv
REPORT_ZIP_PACKAGE.json
```

## Preserve failures

If any failure occurs, save:

```text
outputs\webhard_batch_100\VALIDATION_FAILURES_EXPORT_MEGAPACK.md
```
