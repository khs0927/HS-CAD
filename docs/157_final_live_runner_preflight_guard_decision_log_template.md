# Final Live Runner Preflight Guard Decision Log Template

## Purpose

This document provides the final human decision log template for PR #75.

## Decision log

```text
PR: #75
Branch: feat/final-live-runner-preflight-guard
Main SHA:
Branch SHA:
Branch comparison: behind_by=0 / other
Reviewer:
Local worktree:
Date:
```

## Validation results

```text
Focused tests:
CLI help:
Critical lint:
Full tests:
Forbidden file scan:
Worker manifest direct-edit check:
Duplicate import check:
Docs numbering check:
```

## Decision

Choose one:

```text
APPROVE
REQUEST_CHANGES
BLOCK
```

## Reason

Record the reason for the decision here.

## Required condition

Do not approve if the branch is behind `main`, if duplicate imports exist, if the worker manifest was edited directly, if generated runtime artifacts are staged, or if local validation fails.
