# Final Live Runner Preflight Guard Concurrency Check

## Purpose

This document records the concurrency safeguards for `feat/final-live-runner-preflight-guard` while multiple HS-CAD branches are being worked on in parallel.

## Branch freshness

The branch was compared against `main` after the latest edits.

Expected condition:

```text
base: main
head: feat/final-live-runner-preflight-guard
behind_by: 0
```

If `behind_by` becomes greater than zero before merge, stop and refresh the branch from the latest `main` before continuing.

## Import duplication check

`src/main.py` already contains the preflight CLI import:

```text
import src.app.final_live_runner_preflight_cli  # noqa: F401,E402
```

Do not add it a second time.

## Documentation numbering check

Existing files:

```text
docs/150_final_live_runner_preflight_guard_prompt.md
docs/151_final_live_runner_preflight_guard_report.md
docs/152_final_live_runner_preflight_guard_compliance_report.md
```

This file uses `docs/153_...` to avoid overwriting earlier documents.

## Worker manifest check

Do not edit `config/worker_manifest.json` directly. Use patch JSON files only.

## Commit hygiene check

Do not include generated runtime outputs, archives, local databases, cache folders, or runtime drawing files in this branch.

## Local-only follow-up

The reusable local concurrency checklist is archived on:

```text
archive/hs-cad-local-todos
```
