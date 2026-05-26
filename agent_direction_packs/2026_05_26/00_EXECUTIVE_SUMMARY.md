# 00. Executive Summary

## 현재 핵심 상태

- Repository: `khs0927/HS-CAD`
- Default branch: `main`
- GitHub connector 기준 최신 main commit: `1feb8d3f491b5f2d4253ae44890d9b4bda012701`
- PR #82: closed, not merged, superseded. 직접 머지 금지 유지.
- PR #111: 현재 가장 중요한 검증 대상. Agent 2 candidate validation harness.
- PR #110: docs-only Agent 6 note. PR #111 이후 정리 또는 병합 후보.
- PR #107 / #103: stale docs PR. close 권고.
- PR #105: execution candidate planner이지만 stale, mergeable false, `src/main.py` 포함. 그대로 머지 금지.
- PR #69: FinalLiveRunner. 계속 HOLD.

## 지금 절대 하면 안 되는 일

- PR #82 재오픈 후 직접 머지
- PR #105를 그대로 머지
- PR #69 live runner 머지
- `src/main.py` 또는 `config/worker_manifest.json` 직접 변경
- live CAD 실행 경로 활성화
- SendCommand / SaveAs / DXFOUT / XiCAD alias / 원본 DWG mutation 허용
- 오래된 stacked PR들을 한 번에 처리

## 다음 1순위

1. Agent 3이 PR #111을 로컬에서 quality gate 검증한다.
2. Agent 1이 PR #111 merge 여부를 최종 판단한다.
3. Agent 4가 stale/superseded PR 정리한다.
4. Agent 2는 PR #111 병합 후 다음 검증 하네스 확장 작업을 준비한다.
5. Agent 5는 CI/security workflow를 실제 구현한다.
6. Agent 6은 PR #69 / PR #105 / ODA boundary를 계속 차단·검토한다.

## 한 문장 방향

**기능을 더 추가하지 말고, 현재 들어온 worker/CLI 등록을 검증하는 하네스와 CI 감시 체계를 먼저 완성한다.**
