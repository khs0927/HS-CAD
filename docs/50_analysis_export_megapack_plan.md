# 50. Analysis Export Megapack Plan

## Goal

Continue code generation without validation. All validation remains TODO.

This pack adds:

```text
evidence graph JSONL/CSV export
validation threshold config
report ZIP package scaffold
analysis_export_megapack worker
CLI shortcut v2 scaffold
```

## New worker

```text
analysis_export_megapack
```

Expected command:

```powershell
python -X utf8 -m src.main hscad-worker-run analysis_export_megapack --workspace outputs\webhard_batch_100
```

Optional ZIP creation should remain disabled by default:

```powershell
python -X utf8 -m src.main hscad-worker-run analysis_export_megapack --workspace outputs\webhard_batch_100
```

Later, after review:

```powershell
python -X utf8 -m src.main hscad-worker-run analysis_export_megapack --workspace outputs\webhard_batch_100 --option create_zip=true
```

## Outputs

```text
VALIDATION_THRESHOLDS.json
VALIDATION_THRESHOLD_CONFIG.json
VALIDATION_THRESHOLD_CONFIG.md
EVIDENCE_GRAPH_EXPORT.json
EVIDENCE_GRAPH_EXPORT.md
evidence_graph/nodes.jsonl
evidence_graph/edges.jsonl
evidence_graph/nodes.csv
evidence_graph/edges.csv
REPORT_ZIP_PACKAGE.json
REPORT_ZIP_PACKAGE.md
```

## Validation TODO

Do not run validation now. Preserve this TODO.

```powershell
python -m pytest tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run analysis_export_megapack --workspace outputs\webhard_batch_100
```

## Next TODO

```text
register analysis_export_megapack in worker_manifest.json
wire analysis_shortcut_cli_v2 import into src/main.py
validate CLI shortcut options after worker runner supports --option
add tests after local verification
```
