# 49. Analysis CLI Shortcuts TODO

All validation remains TODO-only.

## New file

```text
src/app/analysis_shortcut_cli.py
```

## Required `src/main.py` patch TODO

```python
import src.app.worker_cli  # noqa: F401,E402
import src.app.analysis_shortcut_cli  # noqa: F401,E402
```

## New commands

```powershell
python -X utf8 -m src.main hscad-analysis-run-all --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-analysis-summary --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-analysis-dashboard --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-analysis-package --workspace outputs\webhard_batch_100
```

## Validation TODO

```powershell
chcp 65001
$env:PYTHONIOENCODING='utf-8'
python -X utf8 -m src.main --help
python -X utf8 -m src.main hscad-analysis-run-all --help
python -X utf8 -m src.main hscad-analysis-run-all --workspace outputs\webhard_batch_100 --dry-run
python -X utf8 -m src.main hscad-analysis-run-all --workspace outputs\webhard_batch_100
```

Expected artifacts:

```text
ANALYSIS_RUN_ALL_SUMMARY.json
ANALYSIS_RUN_ALL_SUMMARY.md
VALIDATION_DASHBOARD.html
EVIDENCE_JOIN_FUSION.json
VALIDATION_RULE_RESULTS.json
REPORT_PACKAGE_MANIFEST.json
```

## Safety

No source drawings are mutated. All commands write derived artifacts under `outputs/...`.
