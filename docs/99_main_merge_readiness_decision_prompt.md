# HS-CAD Main Merge Readiness Decision Prompt

## Goal

Generate a main merge readiness decision package after Post-PR53 planning.

This step does not merge main and does not execute CAD.

## Branch

```powershell
git fetch origin integration/post-pr53-main-merge-local-validation
git switch integration/post-pr53-main-merge-local-validation
git switch -c integration/main-merge-readiness-decision
```

## Apply patch ZIP

Save the ZIP at:

```text
C:\Users\user\Downloads\HS-CAD-main-merge-readiness-decision.zip
```

Apply from repo root:

```powershell
cd C:\CODE\HS-CAD
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-main-merge-readiness-decision.zip" -DestinationPath ".\_main_merge_decision_patch" -Force
Copy-Item -Path ".\_main_merge_decision_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

Add to `src/main.py` only if CLI registration is included in this PR:

```python
import src.app.main_merge_readiness_cli  # noqa: F401,E402
```

## Targeted tests

```powershell
python -X utf8 -m pytest -q tests/test_main_merge_readiness_decision.py
python -X utf8 -m src.main --help
```

## Optional CLI smoke

If CLI registration was added:

```powershell
python -X utf8 -m src.main hscad-main-merge-readiness-decision --repo-root . --post-pr53-workspace outputs\post_pr53_main_merge_local_validation --out-dir outputs\main_merge_readiness_decision
```

Expected outputs:

```text
MAIN_MERGE_READINESS_DECISION.json
MAIN_MERGE_READINESS_DECISION.md
MAIN_MERGE_PR_BODY_DRAFT.md
POST_MERGE_LOCAL_VALIDATION_PROMPT.md
```

## Commit

```powershell
git add src/analysis/main_merge_readiness_decision.py
git add src/workers/main_merge_readiness_decision_worker.py
git add src/app/main_merge_readiness_cli.py
git add tests/test_main_merge_readiness_decision.py
git add docs/99_main_merge_readiness_decision_prompt.md
git add docs/100_main_merge_readiness_decision_report.md
git add config/worker_manifest.main_merge_decision.patch.json
git add MAIN_IMPORT_MAIN_MERGE_DECISION_PATCH.txt
git add README_APPLY_MAIN_MERGE_DECISION.md

git commit -m "feat: add main merge readiness decision package"
git push -u origin integration/main-merge-readiness-decision
```

## PR

Base:

```text
integration/post-pr53-main-merge-local-validation
```

Head:

```text
integration/main-merge-readiness-decision
```

Title:

```text
Add main merge readiness decision package
```
