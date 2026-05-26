# Agent 6 PR Status Note

## Purpose

This note continues the Agent 6 docs-only checkpoint after PR #108 was merged.

Agent 6 keeps branch coordination rules visible while parallel agents work on different branches.

## Baseline

PR #108 is merged into `main`.

```text
main_sha_after_pr108 = 1feb8d3f491b5f2d4253ae44890d9b4bda012701
branch = docs/agent6-pr-status-note
pre_work_compare = ahead_by=0, behind_by=0
```

## Active coordination rules

1. Start from latest `main`.
2. Create a new branch for each new task.
3. Compare with `main` before and after work.
4. Stop if `behind_by` is not zero.
5. Recreate from latest `main` instead of repairing a stale branch.
6. Check for duplicate CLI imports before CLI registration work.
7. Use manifest patch files instead of editing the root manifest directly.
8. If a docs number already exists, use the next available number.
9. Do not commit generated outputs, archives, drawing files, caches, or runtime databases.
10. Do not directly merge PR #82.

## Role split

Agent 6 scope:

- docs-only policy notes
- branch hygiene notes
- PR blocker classification
- safe next-step descriptions

Implementation agent scope:

- source changes
- tests
- CLI registration
- patch manifest files
- local validation

## PR classification

Hold / do not directly merge:

- PR #69
- PR #82

Needs fresh-main recreation if still needed:

- PR #105

Docs-only coordination complete:

- PR #108

## Next safe implementation request

If the execution-candidate planner is still desired, the implementation agent should create a fresh branch from latest `main`.

Suggested branch name:

```text
feat/execution-candidate-planner-mainline
```

Required checks:

```text
before work: compare main...new_branch => behind_by=0
after work: compare main...new_branch => behind_by=0
```

## Agent 6 final decision

```text
agent6_can_continue_docs_only = yes
agent6_can_repair_source_prs = no
pr69_direct_merge = no
pr82_direct_merge = no
stale_branch_repair = no
fresh_main_recreation_required = yes
```
