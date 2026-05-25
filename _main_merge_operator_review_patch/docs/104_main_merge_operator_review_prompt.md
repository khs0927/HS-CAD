# HS-CAD Main Merge Operator Review Prompt

## Context

PR #56 is complete:

- Branch: `integration/main-ready-review-only-pipeline`
- PR URL: https://github.com/khs0927/HS-CAD/pull/56
- Source: PR #55 / `integration/main-merge-readiness-decision`
- Merge result: no conflict
- Targeted helper test: `3 passed`
- Full pytest: `206 passed, 16 skipped`
- compileall: passed
- src.main --help: passed
- hscad-pr55-main-ready-validation: passed
- Main-ready judgment: yes

## Goal

Create a main merge operator review package.

This does not merge main. It only creates:

- operator review package
- main merge operator prompt
- post-merge local validation prompt
- manual checklist

## Branch

```powershell
git fetch origin integration/main-ready-review-only-pipeline
git switch integration/main-ready-review-only-pipeline
git switch -c integration/main-merge-operator-review
```

## Apply ZIP

Save ZIP at:

```text
C:\Users\user\Downloads\HS-CAD-main-merge-operator-review.zip
```

Apply:

```powershell
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-main-merge-operator-review.zip" -DestinationPath ".\_main_merge_operator_review_patch" -Force
Copy-Item -Path ".\_main_merge_operator_review_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

Add to `src/main.py` only if desired:

```python
import src.app.main_merge_operator_review_cli  # noqa: F401,E402
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_main_merge_operator_review.py
python -X utf8 -m src.main --help
```

If CLI registered:

```powershell
python -X utf8 -m src.main hscad-main-merge-operator-review --repo-root . --pr56-workspace outputs\pr55_main_ready_review_only_validation --out-dir outputs\main_merge_operator_review
```

## Commit

```powershell
git add src/analysis/main_merge_operator_review.py
git add src/workers/main_merge_operator_review_worker.py
git add src/app/main_merge_operator_review_cli.py
git add tests/test_main_merge_operator_review.py
git add docs/104_main_merge_operator_review_prompt.md
git add docs/105_main_merge_operator_review_report.md
git add config/worker_manifest.main_merge_operator_review.patch.json
git add MAIN_IMPORT_MAIN_MERGE_OPERATOR_REVIEW_PATCH.txt
git add README_APPLY_MAIN_MERGE_OPERATOR_REVIEW.md

git commit -m "chore: add main merge operator review package"
git push -u origin integration/main-merge-operator-review
```

## PR

Base:

```text
integration/main-ready-review-only-pipeline
```

Head:

```text
integration/main-merge-operator-review
```

Title:

```text
Add main merge operator review package
```
