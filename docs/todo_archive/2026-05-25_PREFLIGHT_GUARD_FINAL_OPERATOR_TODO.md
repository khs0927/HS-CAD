# Final Live Runner Preflight Guard Final Operator TODO

Date: 2026-05-25

Stored on `archive/hs-cad-local-todos` for local-only use.

## Final local operator checklist

1. Fetch latest remote refs.
2. Confirm `main` SHA and record it.
3. Confirm `feat/final-live-runner-preflight-guard` is not behind `main`.
4. Confirm no duplicate preflight CLI import exists in `src/main.py`.
5. Confirm docs numbering from 147 to 156 is intact.
6. Confirm `config/worker_manifest.json` is not modified directly.
7. Confirm only worker manifest patch JSON files are included.
8. Run focused preflight guard tests locally.
9. Run critical lint locally if available.
10. Run `src.main --help` locally.
11. Run full pytest locally if available.
12. Confirm no generated output, archive, cache, local DB, or runtime drawing file is staged.
13. Re-run branch comparison immediately before merge.
14. Record the final decision in the PR comment or local review log.

## Stop conditions

Stop if the branch becomes behind `main`, if a duplicate import appears, if forbidden files are staged, or if local validation fails.
