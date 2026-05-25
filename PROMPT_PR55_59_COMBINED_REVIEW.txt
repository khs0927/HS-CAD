# HS-CAD PR #55~#59 Combined Review Prompt

## Goal

Review PR #55~#59 together and create a single human main-merge review package.

This PR does not merge main, execute CAD, call SendCommand, execute XiCAD aliases, or implement final live runner.

## Branch

```powershell
git fetch origin human/main-merge-review-gate
git switch human/main-merge-review-gate
git pull --ff-only
git switch -c review/pr55-59-combined-main-merge-review
```

## Apply ZIP

Save ZIP:

```text
C:\Users\user\Downloads\HS-CAD-pr55-59-combined-review.zip
```

Apply:

```powershell
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-pr55-59-combined-review.zip" -DestinationPath ".\_pr55_59_combined_review_patch" -Force
Copy-Item -Path ".\_pr55_59_combined_review_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

```python
import src.app.pr55_59_combined_review_cli  # noqa: F401,E402
```

## Validate

```powershell
python -X utf8 -m pytest -q tests/test_pr55_59_combined_review.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

If CLI registered:

```powershell
python -X utf8 -m src.main hscad-pr55-59-combined-review --repo-root . --out-dir outputs\pr55_59_combined_review
```

## Expected outputs

```text
PR55_59_COMBINED_REVIEW_PACKAGE.json
PR55_59_COMBINED_REVIEW_PACKAGE.md
PR55_59_OPERATOR_REVIEW_PROMPT.md
PR55_59_POST_MERGE_MANUAL_COMMANDS.json
```

## Commit

```powershell
git add src/analysis/pr55_59_combined_review.py
git add src/workers/pr55_59_combined_review_worker.py
git add src/app/pr55_59_combined_review_cli.py
git add tests/test_pr55_59_combined_review.py
git add docs/141_pr55_59_combined_review_prompt.md
git add docs/142_pr55_59_combined_review_report.md
git add config/worker_manifest.pr55_59_combined_review.patch.json
git add MAIN_IMPORT_PR55_59_COMBINED_REVIEW_PATCH.txt
git add README_APPLY_PR55_59_COMBINED_REVIEW.md
git add PROMPT_PR55_59_COMBINED_REVIEW.txt

git commit -m "review: add PR55-59 combined main merge review package"
git push -u origin review/pr55-59-combined-main-merge-review
```
