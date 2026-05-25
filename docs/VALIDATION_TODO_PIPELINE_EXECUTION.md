# Validation TODO — Pipeline Execution Megapack

All verification is deferred.

## Later checks

```powershell
python -X utf8 -m src.main hscad-analysis-run-all-exec --workspace outputs\webhard_batch_100 --dry-run
python -X utf8 -m src.main hscad-analysis-report-exec --workspace outputs\webhard_batch_100 --dry-run
python -X utf8 scripts\build_final_codegen_inventory.py
```

## Later non-dry-run

Do not run until imports, worker manifest, and prior megapacks are applied.

```powershell
python -X utf8 -m src.main hscad-analysis-run-all-exec --workspace outputs\webhard_batch_100 --dry-run false
```
