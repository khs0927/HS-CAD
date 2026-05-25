# PR82 Extraction Status Local TODO

Date: 2026-05-26

Stored on `archive/hs-cad-local-todos` for local-only execution.

## Purpose

Validate that the useful PR82 source groups have been extracted into latest main and that PR82 itself remains unmerged.

## Local checklist

1. Pull latest main.
2. Confirm PR82 remains draft or is not merged directly.
3. Run focused spatial tests.
4. Run focused PDF Raster tests.
5. Run focused OCR tests.
6. Run focused NetworkX graph audit tests.
7. Run focused DuckDB analytics tests.
8. Confirm no PR82 ZIP artifacts or runtime output folders are staged.
9. Confirm `src/main.py` and `config/worker_manifest.json` are not changed by candidate extraction work.
10. Record whether any PR82 source group still needs extraction.

## Stop conditions

Stop if runtime/generated artifacts appear in a branch or if high-risk direct edits are staged.
