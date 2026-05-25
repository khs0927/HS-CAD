# HS-CAD Main Merge Manual Runbook

## Rule

Only a human reviewer may decide to merge.

## Pre-merge commands

```powershell
git fetch origin
git switch integration/main-ready-review-only-pipeline
git pull --ff-only
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
python -X utf8 -m src.main hscad-main-merge-readiness-decision --out-dir outputs/human_main_merge_review_decision
```

## Allowed in main

- review-only analysis pipeline
- plan-only Domain Rule bridge
- copied-DWG validation planning
- manual live candidate guard
- safety policy docs
- main-ready validation helpers
- post-main planning docs

## Not allowed in main

- final live runner
- ZWCAD COM SendCommand execution
- XiCAD alias execution
- Domain Rule Command Plan execution
- copied-DWG live validation during merge
- original DWG mutation
- automatic operator approval
