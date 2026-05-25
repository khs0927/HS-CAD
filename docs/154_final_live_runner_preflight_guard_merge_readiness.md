# Final Live Runner Preflight Guard Merge Readiness

## Purpose

This document records the merge-readiness checks for PR #75.

## Branch

```text
feat/final-live-runner-preflight-guard
```

## Base rule

The branch must stay based on the latest `main` before merge.

Current expected condition:

```text
behind_by: 0
```

If `behind_by` becomes greater than zero, refresh the branch before merging.

## Import check

`src/main.py` should contain only one preflight guard CLI import.

Expected import:

```text
import src.app.final_live_runner_preflight_cli  # noqa: F401,E402
```

Do not add a duplicate import.

## Documentation check

Existing sequence:

```text
docs/150_final_live_runner_preflight_guard_prompt.md
docs/151_final_live_runner_preflight_guard_report.md
docs/152_final_live_runner_preflight_guard_compliance_report.md
docs/153_final_live_runner_preflight_guard_concurrency_check.md
```

This file uses `154` and does not overwrite earlier files.

## Manifest check

Do not edit `config/worker_manifest.json` directly. Use only patch JSON files for worker manifest changes.

## Commit hygiene

The PR should contain source, tests, docs, patch JSON, and README/import patch notes only. Generated runtime artifacts should not be included.

## Merge-readiness decision

This PR is ready for local validation and human review when:

- branch is behind-zero against main
- focused tests pass locally
- CLI help works locally
- critical lint passes locally if available
- full tests pass locally if available
- forbidden files are not staged
