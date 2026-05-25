# Final Live Runner Preflight Guard Local Concurrency TODO

Date: 2026-05-25

This local-only TODO is stored separately on `archive/hs-cad-local-todos`.

## Purpose

When multiple HS-CAD branches are being updated at the same time, the local operator should re-check branch freshness before committing or merging.

## Local checklist

1. Fetch the latest remote refs.
2. Confirm the work branch is based on the latest main.
3. Confirm no duplicate import was added to `src/main.py`.
4. Confirm docs 150 and 151 were not overwritten.
5. Confirm `config/worker_manifest.json` was not edited directly.
6. Confirm only patch JSON files were added for worker manifest changes.
7. Confirm generated outputs, drawing runtime files, archives, and caches are not staged.
8. Run focused tests, critical lint, CLI help, and full pytest if available.
9. Re-run branch comparison immediately before final report or merge.

## Branch

`feat/final-live-runner-preflight-guard`

## Notes

If the branch is no longer behind-zero against main, stop and rebase or recreate from current main before continuing.
