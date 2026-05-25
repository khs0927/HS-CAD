# HS-CAD Local Validation TODO Archive

Date: 2026-05-25

This branch keeps local-only validation notes separate from feature branches so the checklist can be reused later.

## Current stacked work

1. PR #66: review-only main-code pipeline and evidence bridge.
2. PR #68: schema-aware evidence bridge mapping.
3. PR #70: review output quality planning.
4. PR #71: megapack finalization workflow.

## Local-only tasks

These steps should be performed in a clean local worktree after the stacked PRs are available locally.

```powershell
cd C:\CODE\HS-CAD-main-code-overlay
git fetch origin --prune
git switch -c feature/hs-cad-megapack-finalization-local origin/feature/hs-cad-megapack-finalization
```

Apply the provided megapack or review-output package in a temporary incoming folder, then run:

```powershell
python -X utf8 -m pytest -q tests/test_legacy_artifact_schema_v6.py
python -X utf8 -m pytest -q tests/test_review_dxf_output_v7.py
python -m ruff check . --select F821,E9,F63,F7,F82
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
```

## Keep out of commits

- generated output folders
- temporary incoming folders
- zip archives
- database files
- cache folders
- runtime drawing artifacts

## Recommended stack order

```text
PR #66
→ PR #68
→ PR #70
→ PR #71
→ validated implementation PRs
```

## Status

Archived for later reuse.
