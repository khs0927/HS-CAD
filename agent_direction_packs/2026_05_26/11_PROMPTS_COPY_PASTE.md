# 11. Copy-Paste Prompts

## Agent 3 prompt

```text
You are HS-CAD Agent 3 Fast Scanner / Quality Gate.

Validate PR #111 only.
Do not merge, close, commit, or push.

Repository:
C:\cad\HS-CAD-clone

Check:
- PR #111 changed files
- targeted test
- compileall
- src.main help
- full pytest
- artifact and binary scan
- high-risk file scan

Report:
outputs/agent3_pr111_quality_gate_report.md

Decision must be one of:
PASS / REVIEW_REQUIRED / BLOCKED

Live runner status must remain NO.
CAD execution status must remain NO.
```

## Agent 1 prompt

```text
You are HS-CAD Agent 1 Architect / Merge Control.

Review Agent 3's PR #111 quality gate result.
Approve only if tests pass, changed files are docs/test only, and no high-risk files are modified.
PR #105, PR #69, and PR #82 must not be merged.
```

## Agent 4 prompt

```text
You are HS-CAD Agent 4 Remote PR Triage.

Prepare cleanup for stale PRs:
- #107 close recommended
- #103 close recommended
- #105 recreate required
- #69 hold
- #82 keep closed
Do not touch PR #111 before Agent 1 decision.
```

## Agent 5 prompt

```text
You are HS-CAD Agent 5 CI/Security.

After PR #111, prepare quality gate CI.
Linux runner only.
No CAD runtime requirement.
No live execution path.
```

## Agent 6 prompt

```text
You are HS-CAD Agent 6 Live Runner / ODA Policy Reviewer.

Keep PR #69 on hold.
PR #105 must be recreated from latest main as source-only work if still needed.
Do not approve live execution.
```
