# 02. Open PR Decision Matrix

## 즉시 집중 대상

| PR | 제목 | 상태 | 판단 | 이유 | 담당 |
|---|---|---:|---|---|---|
| #111 | Add Agent 2 candidate validation harness | open / mergeable true | MERGE_CANDIDATE_AFTER_LOCAL_GATE | docs/test 2개만 변경. worker/CLI candidate validation harness. | Agent 3 검증 → Agent 1 판단 |
| #110 | Add Agent 6 PR status note | open / mergeable true | REVIEW_AFTER_111 | docs-only. 역할/정책 정리. 문서 번호 중복 가능성만 확인. | Agent 1 / Agent 6 |
| #107 | Add current open PR triage table | open / mergeable false | CLOSE_RECOMMENDED | stale docs PR. base가 오래됨. 최신 main과 불일치. | Agent 4 |
| #105 | Add execution candidate planner | open / mergeable false | BLOCKED_RECREATE_REQUIRED | `src/main.py` 포함, stale, direct merge 금지. | Agent 6 정책 검토 → Agent 2 재작성 |
| #103 | Add PR82 extraction status | open / mergeable false | CLOSE_RECOMMENDED | stale docs-only PR. PR82는 이미 closed. | Agent 4 |
| #82 | Review PR38 generated megapack validation branch | closed / not merged | CLOSED_SUPERSEDED | 직접 merge 금지. 이미 작은 PR로 분해됨. | 유지 |
| #69 | FinalLiveRunner | open | HOLD_BLOCKED | live runner 구현 PR. 정책상 진행 금지. | Agent 6 |

## 오래된 stacked / experimental PR

아래 PR들은 지금 당장 처리하지 않는다.

- #12, #16, #20~#58
- #66~#76
- #23~#38 계열 megapack/experimental PR
- #24, #26, #28, #30, #31, #33, #37 experimental domain/CAD execution harness 계열

판단:

- 일부는 이미 main에 유사 내용이 반영됐을 수 있다.
- 일부는 base가 매우 오래됐거나 stacked 구조다.
- quality gate와 PR cleanup 기준이 생기기 전에는 병합하지 않는다.

## 우선 처리 순서

1. PR #111 local quality gate
2. PR #111 merge 판단
3. PR #110 docs-only 검토
4. PR #107/#103 close
5. PR #105 recreate plan 작성
6. PR #69 hold 유지
7. 오래된 PR 전체 triage batch 생성
