# 54. Pipeline Execution Megapack Plan

## Goal

Continue code generation without validation.

This pack adds:

```text
pipeline execution reporter
actual CLI execution scaffolds
final codegen inventory generator
```

## New CLI commands

```text
hscad-analysis-run-all-exec
hscad-analysis-report-exec
```

Both default to:

```text
dry_run=True
```

## Expected commands later

```powershell
python -X utf8 -m src.main hscad-analysis-run-all-exec --workspace outputs\webhard_batch_100 --dry-run
python -X utf8 -m src.main hscad-analysis-report-exec --workspace outputs\webhard_batch_100 --dry-run
python -X utf8 scripts\build_final_codegen_inventory.py
```

## Outputs

```text
outputs\webhard_batch_100\pipeline_execution\PIPELINE_EXECUTION_REPORT.json
outputs\webhard_batch_100\pipeline_execution\PIPELINE_EXECUTION_REPORT.md
outputs\FINAL_CODEGEN_INVENTORY.json
outputs\FINAL_CODEGEN_INVENTORY.md
```

## Validation TODO

No validation now. Later:

```powershell
python -X utf8 -m src.main hscad-analysis-run-all-exec --workspace outputs\webhard_batch_100 --dry-run
```

## Manual patch TODO

Add this import to `src/main.py`:

```python
import src.app.analysis_pipeline_cli  # noqa: F401,E402
```
