# HS-CAD PR #55~#59 Combined Review

## Intended path

```text
C:\Users\user\Downloads\HS-CAD-pr55-59-combined-review.zip
```

## Apply

```powershell
cd C:\CODE\HS-CAD
git fetch origin human/main-merge-review-gate
git switch human/main-merge-review-gate
git pull --ff-only
git switch -c review/pr55-59-combined-main-merge-review

Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-pr55-59-combined-review.zip" -DestinationPath ".\_pr55_59_combined_review_patch" -Force
Copy-Item -Path ".\_pr55_59_combined_review_patch\*" -Destination "." -Recurse -Force
```

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_pr55_59_combined_review.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

## Safety

This package does not merge main, execute CAD, or implement final live runner.
