# Post-Merge Preflight Local TODO

Date: 2026-05-26

Stored on `archive/hs-cad-local-todos` for local-only execution.

## Purpose

PR #75 has been merged into `main`. The local operator should validate the merged preflight guard from a clean latest-main worktree before any next implementation branch starts.

## Local checklist

1. Fetch and pull latest `main`.
2. Record the latest `main` SHA.
3. Run focused preflight guard tests.
4. Run ZWCAD COM evidence probe tests.
5. Run `src.main --help` and confirm CLI visibility.
6. Run critical lint if available.
7. Run full pytest if available.
8. Confirm generated output folders, archives, local databases, cache folders, and runtime drawing files are not staged.
9. Record the local validation result before starting any implementation branch.

## Stop conditions

Stop if local validation fails, if runtime artifacts are staged, or if another main commit appears before the final report.
