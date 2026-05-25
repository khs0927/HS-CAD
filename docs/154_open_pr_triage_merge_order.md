# 154. Open PR Triage and Merge Order

Date: 2026-05-25

This document classifies the currently open HS-CAD pull requests and proposes a safe merge order while multiple agents are working in parallel.

## Current baseline

```text
main SHA: 34759a24158169284824d20b3b2e6a5f2dd2bf31
```

This document was created as a docs-only task. It does not modify code, CLI registration, worker manifest, CAD adapters, or live runner files.

## Global safety rule

Until the safety stack is merged and locally validated, the project default remains:

```text
review-only
plan-only
dry-run-only
no CAD mutation
no SendCommand
no SaveAs
no XiCAD alias execution
no original DWG mutation
```

## PR groups

### Group A: coordination docs

These are documentation-only and can be merged first if they remain clean and mergeable.

| PR | Title | Recommendation |
|---:|---|---|
| #78 | Add parallel work conflict control TODO | Merge first |
| #79 | Add local agent TODO checklist | Merge after #78 |
| #67 | Human verification pack after remote merge | Review after #78/#79 |

Reason: these PRs reduce coordination risk and do not alter runtime behavior.

### Group B: safety and evidence foundation

These should be reviewed before any live runner implementation.

| PR | Title | Recommendation |
|---:|---|---|
| #72 | Add ZWCAD COM evidence probe | Review carefully; read-only evidence only |
| #73 | Approve final live runner safety spec for design after COM probe | Review after #72 |
| #75 | Add final live runner preflight guard | Primary next implementation candidate |
| #77 | Add manual copy-only interface | Review only after #75 is stable |

Reason: this stack keeps live execution blocked while adding evidence, safety decision, preflight refusal, and manual copy-only interfaces.

### Group C: live execution risk

These must remain on hold until Group B is merged and locally validated.

| PR | Title | Recommendation |
|---:|---|---|
| #69 | feat: implement FinalLiveRunner and register ZWCAD live runner CLIs | HOLD |

Hold reason:

```text
live runner implementation + ZWCAD runner CLI registration = high-risk scope
```

Do not merge #69 until:

1. PR #75 preflight guard is merged.
2. PR #77 copy-only interface is validated.
3. A copied-DWG-only execution policy is approved.
4. A rollback/backup manifest path is proven.
5. A human approval gate is explicitly required.

### Group D: stacked feature roadmap and evidence bridge chain

These are stacked and should not be merged out of order.

| PR | Base | Head | Recommendation |
|---:|---|---|---|
| #66 | integration/main-merge-operator-review | feature/main-code-pipeline-overlay | Keep stacked; validate base chain |
| #68 | feature/main-code-pipeline-overlay | feature/evidence-bridge-schema-golden | Merge only after #66 base chain is clear |
| #70 | feature/evidence-bridge-schema-golden | feature/review-output-quality-v2 | Merge only after #68 |
| #71 | feature/review-output-quality-v2 | feature/hs-cad-megapack-finalization | Merge only after #70 |
| #74 | feature/hs-cad-megapack-finalization | feature/megapack-next | Merge only after #71 |
| #76 | feature/megapack-next | feature/roadmap-next-wave | Merge only after #74 |

Reason: these PRs are base-branch dependent. Merging out of order can create duplicate docs, duplicate CLI registrations, or missing parent artifacts.

### Group E: older integration readiness chain

These PRs appear to form a local-validation/main-readiness chain.

| PR | Base | Head | Recommendation |
|---:|---|---|---|
| #52 | reg/final-analysis-worker-manifest | integration/final-review-pipeline-readiness | Validate chain root first |
| #53 | integration/final-review-pipeline-readiness | integration/main-readiness-local-validation-plan | Depends on #52 |
| #54 | integration/main-readiness-local-validation-plan | integration/post-pr53-main-merge-local-validation | Depends on #53 |
| #55 | integration/post-pr53-main-merge-local-validation | integration/main-merge-readiness-decision | Depends on #54 |
| #57 | integration/main-ready-review-only-pipeline | integration/main-merge-operator-review | Needs base verification |
| #58 | integration/main-merge-operator-review | planning/post-main-local-validation-live-runner-safety | Needs #57/base verification |

Recommendation:

```text
Do not merge these directly into main until their full stack root and current main relation are reviewed.
```

## Recommended immediate order

### Step 1: merge coordination docs

```text
#78 -> #79
```

Then local agents must follow:

```text
docs/152_parallel_work_conflict_todo.md
docs/153_local_agent_todo_checklist.md
```

### Step 2: validate safety foundation

```text
#72 -> #73 -> #75 -> #77
```

But merge only after targeted local validation.

Required checks:

```powershell
python -X utf8 -m compileall -q src tests
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q tests/test_final_live_runner_preflight_guard.py
```

### Step 3: keep live runner on hold

```text
#69 = hold
```

Required before reconsidering #69:

```text
- copied-DWG-only test evidence
- explicit backup/rollback manifest
- explicit refusal path
- no original DWG mutation proof
- human approval gate
```

### Step 4: resolve stacked PR chains separately

Do not mix Group D and Group E into the same main merge attempt.

## Conflict scan checklist for every PR before merge

Before merging any PR, verify:

```text
[ ] Is the PR base branch main or a feature branch?
[ ] Is it behind main?
[ ] Does it modify src/main.py?
[ ] Does it modify config/worker_manifest.json?
[ ] Does it introduce live CAD execution?
[ ] Does it introduce SendCommand, SaveAs, DXFOUT, or XiCAD alias execution?
[ ] Does it add outputs, DWG, DXF, ZIP, SQLite, or cache files?
[ ] Are tests listed in the PR body actually run locally?
[ ] Is there a human-readable runbook or refusal path?
```

## Local TODO requirement

Every local agent should leave either:

```text
outputs/local_agent_todo_result.md
```

or a committed docs result when outputs are not intended for commit.

Minimum content:

```text
branch
base main SHA before work
base main SHA after work
files touched
high-risk files touched yes/no
tests run
main moved during work yes/no
next action
```

## This document's final check

At creation time, this PR should contain only:

```text
docs/154_open_pr_triage_merge_order.md
```

No source code, worker manifest, CLI registration, CAD adapter, or runtime output should be modified.
