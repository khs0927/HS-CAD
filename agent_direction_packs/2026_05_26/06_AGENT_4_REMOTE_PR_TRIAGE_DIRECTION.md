# 06. Agent 4 – Remote PR Triage Direction

## 역할

Agent 4는 GitHub PR 정리 담당이다. merge 판단은 Agent 1의 결정을 따른다.

## 바로 할 일

1. PR #82가 closed/not merged 상태인지 재확인하고 그대로 둔다.
2. PR #107 close 권고 또는 close.
3. PR #103 close 권고 또는 close.
4. PR #105에 stale / recreate required 코멘트를 남긴다.
5. PR #69에 HOLD 상태를 유지한다.
6. PR #111은 Agent 3 검증과 Agent 1 판단 전까지 merge하지 않는다.

## 권장 comment

### PR #107

```text
Closing recommended: this docs-only triage PR is stale against the current main. Current PR triage should be regenerated after PR #111 / Agent 1 decision.
```

### PR #103

```text
Closing recommended: PR82 extraction status is now superseded. PR #82 is already closed and the useful parts were split into smaller PRs.
```

### PR #105

```text
Do not merge as-is. This PR is stale, mergeable=false, and touches src/main.py. Recreate from latest main as a source-only execution-candidate planner without direct CLI registration.
```

### PR #69

```text
Live runner remains on HOLD. No SendCommand, SaveAs, DXFOUT, XiCAD alias execution, or original DWG mutation may be enabled.
```

## 금지

- PR #105 merge
- PR #69 merge
- PR #82 reopen
- 오래된 stacked PR 일괄 merge
