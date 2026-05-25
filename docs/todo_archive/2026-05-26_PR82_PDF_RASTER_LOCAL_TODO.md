# PR82 PDF Raster Local Validation TODO

Date: 2026-05-26

Stored on `archive/hs-cad-local-todos` for local-only execution.

## Purpose

Validate the PDF Raster extraction branch from a clean latest-main worktree.

## Local checklist

1. Fetch latest main.
2. Check out the PDF Raster extraction branch.
3. Confirm the branch does not change `src/main.py`.
4. Confirm the branch does not change `config/worker_manifest.json`.
5. Confirm temporary/generated local files are not staged.
6. Run focused PDF Raster tests.
7. Run compile checks for `src/pdf_raster`, `src/workers`, and tests.
8. Optionally test with a sample PDF in an ignored local workspace.
9. Record local results in the PR body or local review notes.
10. Re-compare against latest main before final merge.

## Expected focused checks

- `tests/test_pdf_raster_worker.py`
- compile check for `src/pdf_raster`, `src/workers`, and tests

## Stop conditions

Stop if high-risk file edits appear or generated local artifacts are staged.
