# Final Live Runner Preflight Guard Merge Readiness Local TODO

Date: 2026-05-25

This local-only checklist is archived separately on `archive/hs-cad-local-todos`.

## Purpose

Before PR #75 is merged, the local operator should verify that the branch is still fresh, tests pass, and no runtime artifacts are staged.

## Local-only checklist

1. Fetch latest remote refs.
2. Confirm `feat/final-live-runner-preflight-guard` is still behind-zero against `main`.
3. Confirm `src/main.py` has only one `final_live_runner_preflight_cli` import.
4. Confirm docs 150, 151, 152, 153 were not overwritten.
5. Confirm `config/worker_manifest.json` is unchanged.
6. Confirm worker manifest changes are patch-json only.
7. Run focused preflight guard tests.
8. Run compile check if available.
9. Run critical lint if available.
10. Run `src.main --help` and verify the CLI appears.
11. Run the full test suite if available.
12. Confirm generated output folders, archives, local databases, cache folders, and runtime drawing files are not staged.
13. Re-run branch comparison immediately before merge.

## Result format

Record:

- branch
- main SHA
- behind/ahead status
- test results
- lint result
- CLI help result
- forbidden file check
- final decision
