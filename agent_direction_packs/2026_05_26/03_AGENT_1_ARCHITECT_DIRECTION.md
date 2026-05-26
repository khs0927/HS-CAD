# 03. Agent 1 – Architect / Merge-Control Direction

## 역할

Agent 1은 최종 merge 판단자다. 코드를 많이 쓰지 말고, architecture / safety / merge order를 통제한다.

## 지금 해야 할 일

1. PR #111을 Agent 3 검증 결과 이후 최종 판단한다.
2. PR #111이 아래 조건을 만족하면 squash merge를 승인한다.
   - 변경 파일이 `docs/164_agent2_candidate_validation_harness.md`, `tests/test_agent2_candidate_validation_harness.py` 정도로 제한됨
   - `src/main.py` 미수정
   - `config/worker_manifest.json` 미수정
   - `.github/workflows/*.yml` 미수정
   - full pytest 통과
   - live CAD 실행 없음
3. PR #110은 PR #111 이후 docs-only로 유효한지 판단한다.
4. PR #105는 그대로 merge 금지. 필요하면 최신 main에서 재작성하도록 지시한다.
5. PR #69은 계속 HOLD.
6. PR #107/#103은 stale close 권고를 확정한다.

## 금지

- PR #82 재오픈/직접 merge
- PR #105 직접 merge
- PR #69 merge
- stale stacked PR batch merge
- `src/main.py`, `worker_manifest` 직접 편집 승인

## Agent 1 최종 판단 문구

- PR #111: `MERGE_CANDIDATE_AFTER_AGENT3_PASS`
- PR #105: `BLOCKED_RECREATE_FROM_MAIN_REQUIRED`
- PR #69: `HOLD_LIVE_RUNNER`
- PR #82: `CLOSED_SUPERSEDED_DO_NOT_REOPEN`
