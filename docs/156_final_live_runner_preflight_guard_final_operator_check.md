# Final Live Runner Preflight Guard Final Operator Check

## Purpose

This document is the final operator-facing checklist for PR #75 before merge.

## Required final checks

1. Confirm the branch is still behind-zero against `main`.
2. Confirm `src/main.py` does not contain duplicate preflight CLI imports.
3. Confirm docs 147 through 156 are intact and were not overwritten.
4. Confirm worker manifest integration is represented by patch JSON files only.
5. Confirm generated runtime files are not included in the PR.
6. Confirm local focused tests have been run by the operator.
7. Confirm local CLI help has been checked by the operator.
8. Confirm full local tests have been run where available.
9. Confirm the PR still does not make the final live runner production-ready.

## Branch comparison rule

Expected final condition:

```text
base: main
head: feat/final-live-runner-preflight-guard
behind_by: 0
```

If this condition is not true, refresh the branch before merge.

## Local TODO

The local-only checklist is stored on:

```text
archive/hs-cad-local-todos
```

## Operator decision

Merge should proceed only after human review and local validation confirm the above conditions.
