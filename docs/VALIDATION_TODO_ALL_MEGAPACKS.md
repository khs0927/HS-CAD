# HS-CAD Megapack Validation TODO

All validation is intentionally preserved as TODO.

## Start branch TODO

```powershell
git fetch origin analysis-evidence-megapack-pr25
git switch -C local-megapack-final origin/analysis-evidence-megapack-pr25
```

Extract this zip into the repo root, then patch `src/main.py` using `PATCH_MAIN_IMPORT.md`.

## Install TODO

```powershell
python -X utf8 -m pip install -U pip
python -X utf8 -m pip install -r requirements.txt
python -X utf8 -m pip install pytest shapely
```

## Unit smoke TODO

```powershell
python -X utf8 -m pytest tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
```

## Full analysis TODO

```powershell
$WS='outputs\webhard_batch_100'
python -X utf8 -m src.main hscad-analysis-run-all --workspace $WS --dry-run
python -X utf8 -m src.main hscad-analysis-run-all --workspace $WS
python -X utf8 -m src.main hscad-analysis-dashboard --workspace $WS
python -X utf8 -m src.main hscad-analysis-package --workspace $WS
```

## Expected key outputs

```text
TEXT_ROLE_INFERENCE.json
GEOMETRY_LOOP_BUILDER.json
REAL_GEOMETRY_POLYGONIZER.json
SPATIAL_INDEX_SERVICE.json
TABLE_CELL_EXTRACTOR.json
TITLEBLOCK_KEY_VALUES.json
LAYER_PROFILE_SAMPLE.json
DRAWING_SHEET_CLASSIFIER.json
BATCH_VALIDATION_SUMMARY.json
QUALITY_DASHBOARD_MANIFEST.json
VALIDATION_DASHBOARD.html
EVIDENCE_JOIN_FUSION.json
VALIDATION_RULE_RESULTS.json
REPORT_PACKAGE_MANIFEST.json
CLI_SHORTCUT_PLAN.json
ANALYSIS_RUN_ALL_SUMMARY.json
ANALYSIS_RUN_ALL_SUMMARY.md
```

## Do not mutate

Do not open/save/modify source DWG/PDF/image files. Only write derived artifacts under `outputs/...`.
