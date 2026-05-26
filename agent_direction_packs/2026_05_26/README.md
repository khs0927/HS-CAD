# HS-CAD GitHub Current-State Direction Pack

작성일: 2026-05-26  
Repository: `khs0927/HS-CAD`  
검토 기준 main commit: `1feb8d3f491b5f2d4253ae44890d9b4bda012701`

이 패키지는 GitHub 현재 상태를 전면 검토한 뒤, Agent 1~6이 앞으로 벗어나지 않고 진행해야 할 방향을 정리한 지시 파일 묶음입니다.

## 포함 파일

1. `00_EXECUTIVE_SUMMARY.md`
2. `01_CURRENT_GITHUB_STATE.md`
3. `02_OPEN_PR_DECISION_MATRIX.md`
4. `03_AGENT_1_ARCHITECT_DIRECTION.md`
5. `04_AGENT_2_IMPLEMENTATION_DIRECTION.md`
6. `05_AGENT_3_QUALITY_GATE_WATCHER_DIRECTION.md`
7. `06_AGENT_4_REMOTE_PR_TRIAGE_DIRECTION.md`
8. `07_AGENT_5_CI_SECURITY_DIRECTION.md`
9. `08_AGENT_6_LIVE_RUNNER_ODA_POLICY_DIRECTION.md`
10. `09_NEXT_72_HOURS_SEQUENCE.md`
11. `10_SAFETY_BOUNDARIES.md`
12. `11_PROMPTS_COPY_PASTE.md`

## 최우선 결론

- PR #82는 이미 closed / not merged 상태이며, 직접 머지 금지 상태를 유지한다.
- 현재 가장 우선 처리할 PR은 PR #111이다.
- PR #111은 Agent 2 candidate validation harness이며, 변경 파일이 docs/test 2개뿐이라 우선 검증 대상이다.
- PR #105는 stale + `src/main.py` 포함 + mergeable false이므로 그대로 머지 금지다.
- PR #69 FinalLiveRunner는 계속 HOLD다.
- 다음 개발의 중심은 기능 추가가 아니라 `worker/CLI validation harness`와 `GitHub quality gate` 구축이다.
